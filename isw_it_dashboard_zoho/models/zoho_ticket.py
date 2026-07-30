import hashlib
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone

import requests

from odoo import _, api, fields, models
from odoo.osv import expression
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ITZohoTicket(models.Model):
    _name = "it.zoho.ticket"
    _description = "Zoho Desk Ticket"
    _order = "created_time desc, id desc"

    zoho_ticket_id = fields.Char(string="Zoho Ticket ID", required=True, index=True, copy=False)
    ticket_number = fields.Char(string="Ticket Number", index=True)
    layout_id_external = fields.Char(string="Zoho Layout ID")
    subject = fields.Char(required=True)
    email = fields.Char()
    phone = fields.Char()
    department_id_external = fields.Char(string="Zoho Department ID", index=True)
    department_name = fields.Char()
    channel = fields.Char(index=True)
    channel_code = fields.Char()
    status = fields.Char(index=True)
    status_type = fields.Char(index=True)
    priority = fields.Char(index=True)
    classification = fields.Char(
        string="Classification",
        index=True,
        tracking=True,
        help="Ticket classification captured from Zoho Desk (for example Request or Problem).",
    )
    category = fields.Char(index=True)
    subcategory = fields.Char()
    language = fields.Char()
    sentiment = fields.Char()
    created_time = fields.Datetime(index=True)
    modified_time = fields.Datetime(index=True)
    due_date = fields.Datetime()
    response_due_date = fields.Datetime()
    customer_response_time = fields.Datetime()
    first_response_time = fields.Datetime(string="First Agent Response At", index=True)
    closed_time = fields.Datetime(index=True)
    on_hold_time = fields.Datetime()

    # Normalized metric values. Seconds are the canonical reporting values.
    first_response_time_seconds = fields.Integer(string="First Response Time (Seconds)", index=True)
    total_response_time_seconds = fields.Integer(string="Total Response Time (Seconds)", index=True)
    average_response_time_seconds = fields.Integer(string="Average Response Time (Seconds)", index=True)
    resolution_time_seconds = fields.Integer(string="Resolution Time (Seconds)", index=True)
    first_response_minutes = fields.Float(string="First Response Time (Minutes)", compute="_compute_metric_minutes", store=True)
    total_response_time_minutes = fields.Float(string="Total Response Time (Minutes)", compute="_compute_metric_minutes", store=True)
    response_time_minutes = fields.Float(string="Average Response Time (Minutes)", compute="_compute_metric_minutes", store=True)
    resolution_time_minutes = fields.Float(string="Resolution Time (Minutes)", compute="_compute_metric_minutes", store=True)
    calendar_resolution_time_minutes = fields.Float(string="Calendar Resolution Time (Minutes)", readonly=True)
    response_count = fields.Integer(string="Response Count")
    outgoing_count = fields.Integer(string="Outgoing Count")
    metrics_thread_count = fields.Integer(string="Metrics Thread Count")
    reopen_count = fields.Integer(string="Reopen Count")
    reassign_count = fields.Integer(string="Reassign Count")
    stage_metric_ids = fields.One2many(
        "it.zoho.ticket.stage.metric", "ticket_id", string="Status Handling Metrics", readonly=True
    )
    agent_metric_ids = fields.One2many(
        "it.zoho.ticket.agent.metric", "ticket_id", string="Agent Handling Metrics", readonly=True
    )
    sla_violated = fields.Boolean(index=True)
    first_response_sla_violated = fields.Boolean(string="First Response SLA Violated", index=True)
    resolution_sla_violated = fields.Boolean(string="Resolution SLA Violated", index=True)
    customer_rating = fields.Float()

    metrics_sync_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("success", "Success"),
            ("failed", "Failed"),
            ("not_available", "Not Available"),
        ],
        default="pending",
        index=True,
        readonly=True,
    )
    metrics_sync_attempts = fields.Integer(default=0, readonly=True)
    metrics_next_retry = fields.Datetime(index=True, readonly=True)
    metrics_payload_hash = fields.Char(index=True, readonly=True)
    metrics_last_sync = fields.Datetime(readonly=True, index=True)
    metrics_error = fields.Text(readonly=True)
    metrics_raw_payload = fields.Text(readonly=True)

    assignee_id_external = fields.Char(string="Zoho Assignee ID", index=True)
    assignee_name = fields.Char()
    account_id_external = fields.Char(string="Zoho Account ID")
    account_name = fields.Char()
    contact_id_external = fields.Char(string="Zoho Contact ID")
    contact_name = fields.Char()
    product_id_external = fields.Char(string="Zoho Product ID")
    team_id_external = fields.Char(string="Zoho Team ID")
    comment_count = fields.Integer()
    thread_count = fields.Integer()
    relationship_type = fields.Char()
    is_archived = fields.Boolean(index=True)
    is_spam = fields.Boolean(index=True)
    web_url = fields.Char()
    last_thread_channel = fields.Char()
    last_thread_direction = fields.Char()
    last_thread_is_draft = fields.Boolean()
    last_thread_is_forward = fields.Boolean()
    source_type = fields.Char()
    source_app_name = fields.Char()
    raw_payload = fields.Text(readonly=True)
    last_sync_date = fields.Datetime(default=fields.Datetime.now, index=True, readonly=True)

    _unique_zoho_ticket = models.Constraint(
        "UNIQUE(zoho_ticket_id)",
        "The Zoho ticket ID must be unique.",
    )

    @api.depends(
        "first_response_time_seconds",
        "total_response_time_seconds",
        "average_response_time_seconds",
        "resolution_time_seconds",
    )
    def _compute_metric_minutes(self):
        for record in self:
            record.first_response_minutes = (record.first_response_time_seconds or 0) / 60.0
            record.total_response_time_minutes = (record.total_response_time_seconds or 0) / 60.0
            record.response_time_minutes = (record.average_response_time_seconds or 0) / 60.0
            record.resolution_time_minutes = (record.resolution_time_seconds or 0) / 60.0

    @api.model
    def _config(self, key, default=False):
        return self.env["ir.config_parameter"].sudo().get_param(
            f"isw_it_dashboard_zoho.{key}", default
        )

    @api.model
    def _set_config(self, key, value):
        self.env["ir.config_parameter"].sudo().set_param(
            f"isw_it_dashboard_zoho.{key}", value or ""
        )

    @api.model
    def _safe_response_error(self, response):
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        return (
            payload.get("error")
            or payload.get("errorCode")
            or payload.get("message")
            or payload.get("error_description")
            or f"HTTP {response.status_code}"
        )

    @api.model
    def _get_access_token(self, force_refresh=False):
        if not force_refresh:
            cached_token = (self._config("access_token") or "").strip()
            expires_at_raw = (self._config("access_token_expires_at") or "").strip()
            if cached_token and expires_at_raw:
                expires_at = fields.Datetime.to_datetime(expires_at_raw)
                if expires_at and expires_at > fields.Datetime.now() + timedelta(seconds=60):
                    return cached_token

        accounts_url = (self._config("accounts_url", "https://accounts.zoho.com") or "").strip().rstrip("/")
        client_id = (self._config("client_id") or "").strip()
        client_secret = (self._config("client_secret") or "").strip()
        refresh_token = (self._config("refresh_token") or "").strip()

        missing = []
        if not client_id:
            missing.append(_("OAuth Client ID"))
        if not client_secret:
            missing.append(_("OAuth Client Secret"))
        if not refresh_token:
            missing.append(_("OAuth Refresh Token"))
        if missing:
            raise UserError(_("Missing Zoho configuration: %s") % ", ".join(missing))

        try:
            response = requests.post(
                f"{accounts_url}/oauth/v2/token",
                data={
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                },
                timeout=30,
            )
        except requests.RequestException as exc:
            _logger.exception("Unable to connect to Zoho OAuth.")
            raise UserError(_("Unable to connect to the Zoho OAuth service.")) from exc

        if not response.ok:
            error = self._safe_response_error(response)
            self._set_config("connection_status", "error")
            self._set_config("last_error", f"OAuth refresh failed: {error}")
            _logger.error("Zoho OAuth refresh failed. status=%s error=%s", response.status_code, error)
            raise UserError(
                _("Zoho OAuth authentication failed. HTTP %(status)s: %(error)s")
                % {"status": response.status_code, "error": error}
            )

        data = response.json()
        token = data.get("access_token")
        if not token:
            raise UserError(_("Zoho did not return an access token."))

        expires_in = int(data.get("expires_in") or 3600)
        expires_at = fields.Datetime.now() + timedelta(seconds=expires_in)
        self._set_config("access_token", token)
        self._set_config("access_token_expires_at", fields.Datetime.to_string(expires_at))
        self._set_config("connection_status", "connected")
        self._set_config("last_error", "")
        return token

    @api.model
    def _headers(self):
        org_id = (self._config("org_id") or "").strip()
        if not org_id:
            raise UserError(_("Zoho Organization ID is not configured."))
        return {
            "Authorization": f"Zoho-oauthtoken {self._get_access_token()}",
            "orgId": org_id,
            "Accept": "application/json",
        }

    @api.model
    def _request(self, method, endpoint, params=None, timeout=60, allow_not_found=False):
        api_base = (self._config("api_base", "https://desk.zoho.com/api/v1") or "").strip().rstrip("/")
        url = f"{api_base}/{endpoint.lstrip('/')}"
        try:
            response = requests.request(method, url, headers=self._headers(), params=params, timeout=timeout)
        except requests.RequestException as exc:
            raise UserError(_("Unable to connect to the Zoho Desk API.")) from exc

        if response.status_code == 401:
            self._get_access_token(force_refresh=True)
            response = requests.request(method, url, headers=self._headers(), params=params, timeout=timeout)

        if allow_not_found and response.status_code in (404, 405):
            return response
        if not response.ok:
            error = self._safe_response_error(response)
            raise UserError(
                _("Zoho Desk request failed. HTTP %(status)s: %(error)s")
                % {"status": response.status_code, "error": error}
            )
        return response

    @api.model
    def _parse_datetime(self, value):
        if not value:
            return False
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return fields.Datetime.to_string(parsed)
        except (TypeError, ValueError):
            _logger.warning("Unable to parse Zoho datetime: %s", value)
            return False

    @api.model
    def _duration_to_seconds(self, value, assume_milliseconds=False):
        """Normalize Zoho duration values to integer seconds.

        Confirmed Zoho metrics examples include ``00:06 hrs`` and ``25:14 hrs``.
        Two-part values are interpreted as hours and minutes.
        """
        if value in (None, False, ""):
            return 0
        if isinstance(value, (int, float)):
            seconds = float(value) / 1000.0 if assume_milliseconds else float(value)
            return max(int(round(seconds)), 0)

        text = str(value).strip().lower()
        text = re.sub(
            r"\s*(hrs?|hours?|mins?|minutes?|secs?|seconds?)\s*$",
            "",
            text,
        ).strip()

        try:
            numeric = float(text)
            seconds = numeric / 1000.0 if assume_milliseconds else numeric
            return max(int(round(seconds)), 0)
        except ValueError:
            pass

        parts = [part.strip() for part in text.split(":")]
        try:
            if len(parts) == 3:
                hours, minutes, seconds = parts
                return max(int(float(hours) * 3600 + float(minutes) * 60 + float(seconds)), 0)
            if len(parts) == 2:
                hours, minutes = parts
                return max(int(float(hours) * 3600 + float(minutes) * 60), 0)
        except (TypeError, ValueError):
            return 0
        return 0

    @api.model
    def _metric_value(self, payload, second_keys, millisecond_keys=()):
        for key in millisecond_keys:
            if payload.get(key) not in (None, False, ""):
                return self._duration_to_seconds(payload.get(key), assume_milliseconds=True)
        for key in second_keys:
            if payload.get(key) not in (None, False, ""):
                return self._duration_to_seconds(payload.get(key))
        return 0

    @api.model
    def _rating_to_float(self, value):
        if value in (None, False, ""):
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            labels = {"bad": 1.0, "poor": 1.0, "okay": 3.0, "neutral": 3.0, "good": 5.0, "happy": 5.0}
            return labels.get(str(value).strip().lower(), 0.0)

    @api.model
    def _ticket_values(self, data):
        assignee = data.get("assignee") if isinstance(data.get("assignee"), dict) else {}
        contact = data.get("contact") if isinstance(data.get("contact"), dict) else {}
        account = data.get("account") if isinstance(data.get("account"), dict) else {}
        department = data.get("department") if isinstance(data.get("department"), dict) else {}
        happiness = data.get("customerHappiness") if isinstance(data.get("customerHappiness"), dict) else {}
        last_thread = data.get("lastThread") if isinstance(data.get("lastThread"), dict) else {}
        source = data.get("source") if isinstance(data.get("source"), dict) else {}

        created_time = self._parse_datetime(data.get("createdTime"))
        closed_time = self._parse_datetime(data.get("closedTime"))
        calendar_resolution_minutes = 0.0
        if created_time and closed_time:
            created_dt = fields.Datetime.to_datetime(created_time)
            closed_dt = fields.Datetime.to_datetime(closed_time)
            calendar_resolution_minutes = max((closed_dt - created_dt).total_seconds() / 60.0, 0.0)

        contact_name = data.get("contactName")
        if not contact_name:
            contact_name = " ".join(part for part in (contact.get("firstName"), contact.get("lastName")) if part)

        return {
            "zoho_ticket_id": str(data.get("id") or ""),
            "ticket_number": data.get("ticketNumber") or "",
            "layout_id_external": str(data.get("layoutId") or ""),
            "subject": data.get("subject") or _("Untitled Zoho Ticket"),
            "email": data.get("email") or "",
            "phone": data.get("phone") or "",
            "department_id_external": str(data.get("departmentId") or department.get("id") or ""),
            "department_name": department.get("name") or data.get("departmentName") or "",
            "channel": data.get("channel") or "",
            "channel_code": data.get("channelCode") or "",
            "status": data.get("status") or "",
            "status_type": data.get("statusType") or "",
            "priority": data.get("priority") or "",
            "classification": data.get("classification") or "",
            "category": data.get("category") or "",
            "subcategory": data.get("subCategory") or "",
            "language": data.get("language") or "",
            "sentiment": data.get("sentiment") or "",
            "created_time": created_time,
            "modified_time": self._parse_datetime(data.get("modifiedTime")),
            "due_date": self._parse_datetime(data.get("dueDate")),
            "response_due_date": self._parse_datetime(data.get("responseDueDate")),
            "customer_response_time": self._parse_datetime(data.get("customerResponseTime")),
            "first_response_time": self._parse_datetime(data.get("firstResponseTime")),
            "closed_time": closed_time,
            "on_hold_time": self._parse_datetime(data.get("onholdTime")),
            "calendar_resolution_time_minutes": calendar_resolution_minutes,
            "sla_violated": bool(data.get("isOverDue") or data.get("slaViolated")),
            "customer_rating": self._rating_to_float(happiness.get("rating") or data.get("rating")),
            "assignee_id_external": str(data.get("assigneeId") or assignee.get("id") or ""),
            "assignee_name": assignee.get("name") or data.get("assigneeName") or "",
            "account_id_external": str(data.get("accountId") or account.get("id") or ""),
            "account_name": account.get("accountName") or data.get("accountName") or "",
            "contact_id_external": str(data.get("contactId") or contact.get("id") or ""),
            "contact_name": contact_name or "",
            "product_id_external": str(data.get("productId") or ""),
            "team_id_external": str(data.get("teamId") or ""),
            "comment_count": int(data.get("commentCount") or 0),
            "thread_count": int(data.get("threadCount") or 0),
            "relationship_type": data.get("relationshipType") or "",
            "is_archived": bool(data.get("isArchived")),
            "is_spam": bool(data.get("isSpam")),
            "web_url": data.get("webUrl") or "",
            "last_thread_channel": last_thread.get("channel") or "",
            "last_thread_direction": last_thread.get("direction") or "",
            "last_thread_is_draft": bool(last_thread.get("isDraft")),
            "last_thread_is_forward": bool(last_thread.get("isForward")),
            "source_type": source.get("type") or "",
            "source_app_name": source.get("appName") or "",
            "raw_payload": json.dumps(data, ensure_ascii=False, indent=2),
            "last_sync_date": fields.Datetime.now(),
        }

    @api.model
    def _metrics_values(self, payload):
        """Map the confirmed Zoho Desk ticket metrics response."""
        metrics = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
        metrics = metrics if isinstance(metrics, dict) else {}

        first_response_seconds = self._duration_to_seconds(metrics.get("firstResponseTime"))
        total_response_seconds = self._duration_to_seconds(metrics.get("totalResponseTime"))
        resolution_seconds = self._duration_to_seconds(metrics.get("resolutionTime"))
        response_count = int(metrics.get("responseCount") or 0)
        average_response_seconds = int(total_response_seconds / response_count) if response_count else 0

        first_response_at = (
            metrics.get("firstResponseAt")
            or metrics.get("firstResponseTimeStamp")
            or metrics.get("firstRespondedTime")
        )

        return {
            "first_response_time_seconds": first_response_seconds,
            "total_response_time_seconds": total_response_seconds,
            "average_response_time_seconds": average_response_seconds,
            "resolution_time_seconds": resolution_seconds,
            "response_count": response_count,
            "outgoing_count": int(metrics.get("outgoingCount") or 0),
            "metrics_thread_count": int(metrics.get("threadCount") or 0),
            "reopen_count": int(metrics.get("reopenCount") or 0),
            "reassign_count": int(metrics.get("reassignCount") or 0),
            "first_response_time": self._parse_datetime(first_response_at),
            "first_response_sla_violated": bool(
                metrics.get("firstResponseSlaViolated")
                or metrics.get("firstResponseViolated")
                or metrics.get("isFirstResponseOverdue")
            ),
            "resolution_sla_violated": bool(
                metrics.get("resolutionSlaViolated")
                or metrics.get("resolutionViolated")
                or metrics.get("isResolutionOverdue")
            ),
            "sla_violated": bool(
                metrics.get("slaViolated")
                or metrics.get("isOverDue")
                or metrics.get("firstResponseSlaViolated")
                or metrics.get("resolutionSlaViolated")
            ),
            "metrics_sync_status": "success",
            "metrics_last_sync": fields.Datetime.now(),
            "metrics_error": False,
            "metrics_raw_payload": json.dumps(payload, ensure_ascii=False, indent=2),
        }

    def _replace_stage_metrics(self, payload):
        self.ensure_one()
        metrics = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
        metrics = metrics if isinstance(metrics, dict) else {}
        self.stage_metric_ids.unlink()
        values = []
        for item in metrics.get("stagingData") or []:
            values.append({
                "ticket_id": self.id,
                "status": item.get("status") or _("Unknown"),
                "handled_time_seconds": self._duration_to_seconds(item.get("handledTime")),
            })
        if values:
            self.env["it.zoho.ticket.stage.metric"].create(values)

    def _replace_agent_metrics(self, payload):
        self.ensure_one()
        metrics = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
        metrics = metrics if isinstance(metrics, dict) else {}
        self.agent_metric_ids.unlink()
        values = []
        for item in metrics.get("agentsHandled") or []:
            values.append({
                "ticket_id": self.id,
                "zoho_agent_id": str(item.get("agentId") or ""),
                "agent_name": item.get("agentName") or _("Unknown"),
                "handling_time_seconds": self._duration_to_seconds(item.get("handlingTime")),
            })
        if values:
            self.env["it.zoho.ticket.agent.metric"].create(values)

    @api.model
    def _metrics_candidate(self, record):
        if self._config("sync_metrics") not in ("True", "1", True):
            return False
        closed_only = self._config("metrics_closed_only") in ("True", "1", True)
        return not closed_only or record.status_type == "Closed" or record.status == "Closed"

    @api.model
    def _upsert_ticket(self, data):
        vals = self._ticket_values(data)
        external_id = vals.get("zoho_ticket_id")
        if not external_id:
            return False, "failed"

        record = self.search([("zoho_ticket_id", "=", external_id)], limit=1)
        tracked = (
            "status", "status_type", "classification", "closed_time", "modified_time",
            "assignee_id_external", "department_id_external",
            "thread_count", "comment_count",
        )
        if not record:
            vals.update({
                "metrics_sync_status": "pending",
                "metrics_sync_attempts": 0,
                "metrics_next_retry": False,
                "metrics_error": False,
            })
            return self.create(vals), "created"

        changed = any(
            name in vals and record[name] != vals[name]
            for name in tracked
        )
        if changed:
            vals.update({
                "metrics_sync_status": "pending",
                "metrics_sync_attempts": 0,
                "metrics_next_retry": False,
                "metrics_error": False,
            })
        record.write(vals)
        return record, "updated"

    def action_sync_metrics(self):
        for record in self:
            record._sync_metrics(raise_on_error=True)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Zoho Ticket Metrics"),
                "message": _("Metrics synchronized for the selected ticket(s)."),
                "type": "success",
                "sticky": False,
            },
        }

    def _sync_metrics(self, raise_on_error=False):
        self.ensure_one()
        endpoint_pattern = (self._config("metrics_endpoint", "tickets/{ticket_id}/metrics") or "").strip()
        endpoint = endpoint_pattern.format(ticket_id=self.zoho_ticket_id)
        self.write({"metrics_sync_status": "processing"})
        try:
            response = self._request("GET", endpoint, timeout=30, allow_not_found=True)
            if response.status_code in (404, 405):
                error = _("The configured Zoho metrics endpoint is not available for this ticket or account.")
                self.write({
                    "metrics_sync_status": "not_available",
                    "metrics_last_sync": fields.Datetime.now(),
                    "metrics_error": error,
                    "metrics_next_retry": False,
                })
                if raise_on_error:
                    raise UserError(error)
                return False

            payload = response.json()
            normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            payload_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            values = self._metrics_values(payload)
            values.update({
                "metrics_payload_hash": payload_hash,
                "metrics_sync_attempts": 0,
                "metrics_next_retry": False,
            })
            payload_changed = self.metrics_payload_hash != payload_hash
            self.write(values)
            if payload_changed:
                self._replace_stage_metrics(payload)
                self._replace_agent_metrics(payload)
            return True
        except Exception as exc:
            error = exc.args[0] if exc.args else str(exc)
            attempts = self.metrics_sync_attempts + 1
            retry_minutes = min(60, max(5, attempts * 5))
            self.write({
                "metrics_sync_status": "failed",
                "metrics_sync_attempts": attempts,
                "metrics_next_retry": fields.Datetime.now() + timedelta(minutes=retry_minutes),
                "metrics_last_sync": fields.Datetime.now(),
                "metrics_error": str(error)[:4000],
            })
            _logger.exception("Zoho metrics synchronization failed for ticket %s", self.zoho_ticket_id)
            if raise_on_error:
                raise
            return False

    @api.model
    def _sync_single_ticket(self, ticket_id):
        response = self._request("GET", f"tickets/{ticket_id}", timeout=30)
        record, outcome = self._upsert_ticket(response.json())
        return outcome

    @api.model
    def test_connection(self):
        response = self._request("GET", "tickets", params={"from": 0, "limit": 1}, timeout=30)
        payload = response.json()
        count = len(payload.get("data", [])) if isinstance(payload, dict) else 0
        self._set_config("connection_status", "connected")
        self._set_config("last_error", "")
        return _("Connection successful. Zoho Desk returned %(count)s test record(s).") % {"count": count}

    @api.model
    def _configured_departments(self):
        return [
            value.strip()
            for value in (self._config("department_ids") or "").split(",")
            if value.strip()
        ] or [False]

    @api.model
    def _get_or_create_sync_state(self, department_id=False):
        State = self.env["it.zoho.sync.state"].sudo()
        domain = [
            ("company_id", "=", self.env.company.id),
            ("department_id", "=", department_id or False),
            ("active", "=", True),
        ]
        state = State.search(domain, limit=1)
        if not state:
            state = State.create({
                "name": _("Zoho Tickets - %s") % (department_id or _("All Departments")),
                "department_id": department_id or False,
                "company_id": self.env.company.id,
                "next_offset": 0,
                "batch_size": max(1, min(int(self._config("ticket_batch_size", 50) or 50), 100)),
            })
        return state

    @api.model
    def sync_ticket_batch(self, raise_on_error=False):
        """Fetch only one Zoho page for one department per execution."""
        empty = {"received": 0, "created": 0, "updated": 0, "failed": 0}
        if self._config("enabled") not in ("True", "1", True):
            if raise_on_error:
                raise UserError(_("Zoho Desk synchronization is disabled."))
            return empty

        departments = self._configured_departments()
        State = self.env["it.zoho.sync.state"].sudo()
        states = State.search([
            ("company_id", "=", self.env.company.id),
            ("active", "=", True),
            ("department_id", "in", [d or False for d in departments]),
        ], order="last_attempt_at asc nulls first, id")
        existing = {s.department_id or False for s in states}
        for department_id in departments:
            if (department_id or False) not in existing:
                self._get_or_create_sync_state(department_id)
        state = State.search([
            ("company_id", "=", self.env.company.id),
            ("active", "=", True),
            ("department_id", "in", [d or False for d in departments]),
        ], order="last_attempt_at asc nulls first, id", limit=1)
        if not state:
            return empty

        configured_size = max(1, min(int(self._config("ticket_batch_size", 50) or 50), 100))
        batch_size = min(state.batch_size or configured_size, configured_size, 100)
        start_offset = max(state.next_offset or 0, 0)
        log = self.env["it.integration.sync.log"].sudo().create({
            "name": _("Zoho Desk Ticket Batch"),
        })
        counts = dict(empty)
        state.write({"current_run_started": fields.Datetime.now(), "last_attempt_at": fields.Datetime.now(), "last_error": False})
        try:
            params = {"from": start_offset, "limit": batch_size, "sortBy": "modifiedTime"}
            if state.department_id:
                params["departmentId"] = state.department_id
            response = self._request("GET", "tickets", params=params, timeout=60)
            payload = response.json()
            tickets = payload.get("data", []) if isinstance(payload, dict) else payload
            tickets = tickets if isinstance(tickets, list) else []
            counts["received"] = len(tickets)
            for data in tickets:
                try:
                    record, outcome = self._upsert_ticket(data)
                    counts[outcome] += 1
                    if record and not self._metrics_candidate(record):
                        record.write({"metrics_sync_status": "not_available"})
                except Exception:
                    counts["failed"] += 1
                    _logger.exception("Zoho ticket mapping failed for ticket ID %s", data.get("id"))

            end_reached = len(tickets) < batch_size
            state.write({
                "next_offset": 0 if end_reached else start_offset + len(tickets),
                "initial_sync_completed": state.initial_sync_completed or end_reached,
                "last_successful_sync": fields.Datetime.now(),
                "current_run_started": False,
                "last_received_count": len(tickets),
                "last_error": False,
            })
            log.write({
                "completed_at": fields.Datetime.now(),
                "status": "partial" if counts["failed"] else "success",
                "records_received": counts["received"],
                "records_created": counts["created"],
                "records_updated": counts["updated"],
                "records_failed": counts["failed"],
                "error_message": _("Department: %(department)s; offset: %(offset)s; next offset: %(next)s") % {
                    "department": state.department_id or _("All"),
                    "offset": start_offset,
                    "next": state.next_offset,
                },
            })
            self._set_config("last_sync_at", fields.Datetime.to_string(fields.Datetime.now()))
            self._set_config("last_error", "")
            return counts
        except Exception as exc:
            safe_error = str(exc.args[0] if exc.args else exc)[:4000]
            state.write({"current_run_started": False, "last_error": safe_error})
            log.write({
                "completed_at": fields.Datetime.now(), "status": "failed",
                "records_received": counts["received"], "records_created": counts["created"],
                "records_updated": counts["updated"], "records_failed": counts["failed"],
                "error_message": safe_error,
            })
            self._set_config("last_error", safe_error)
            _logger.exception("Zoho ticket batch synchronization failed")
            if raise_on_error:
                raise
            return counts

    @api.model
    def _get_or_create_metrics_sync_state(self):
        State = self.env["it.zoho.metrics.sync.state"].sudo()
        state = State.search([("company_id", "=", self.env.company.id)], limit=1)
        if not state:
            state = State.create({
                "name": _("Zoho Desk Metrics Sync"),
                "company_id": self.env.company.id,
                "batch_size": max(1, min(int(self._config("metrics_batch_size", 100) or 100), 500)),
                "time_budget_seconds": max(30, min(int(self._config("metrics_time_budget_seconds", 240) or 240), 1800)),
                "stale_after_hours": max(1, int(self._config("metrics_stale_hours", 6) or 6)),
                "refresh_stale_metrics": self._config("refresh_stale_metrics") in ("True", "1", True),
                "refresh_closed_metrics": self._config("refresh_closed_metrics") in ("True", "1", True),
            })
        return state

    @api.model
    def _metrics_eligible_domain(self):
        domain = []
        if self._config("metrics_closed_only") in ("True", "1", True):
            domain = expression.OR([[('status_type', '=', 'Closed')], [('status', '=', 'Closed')]])
        return domain

    @api.model
    def _pending_metrics_domain(self):
        now = fields.Datetime.now()
        return expression.AND([
            self._metrics_eligible_domain(),
            [
                ("metrics_sync_status", "in", ["pending", "failed"]),
                "|", ("metrics_next_retry", "=", False), ("metrics_next_retry", "<=", now),
            ],
        ])

    @api.model
    def _stale_metrics_domain(self, state):
        if not state.refresh_stale_metrics:
            return [("id", "=", 0)]
        cutoff = fields.Datetime.now() - timedelta(hours=max(1, state.stale_after_hours or 6))
        status_domain = []
        if not state.refresh_closed_metrics:
            status_domain = expression.AND([
                [('status_type', '!=', 'Closed')],
                [('status', '!=', 'Closed')],
            ])
        return expression.AND([
            self._metrics_eligible_domain(),
            status_domain,
            [
                ("metrics_sync_status", "=", "success"),
                "|", ("metrics_last_sync", "=", False), ("metrics_last_sync", "<=", cutoff),
            ],
        ])

    @api.model
    def _update_metrics_sync_state(self, state=None):
        state = state or self._get_or_create_metrics_sync_state()
        eligible_domain = self._metrics_eligible_domain()
        pending_domain = self._pending_metrics_domain()
        values = {
            "batch_size": max(1, min(int(self._config("metrics_batch_size", state.batch_size or 100) or 100), 500)),
            "time_budget_seconds": max(30, min(int(self._config("metrics_time_budget_seconds", state.time_budget_seconds or 240) or 240), 1800)),
            "stale_after_hours": max(1, int(self._config("metrics_stale_hours", state.stale_after_hours or 6) or 6)),
            "refresh_stale_metrics": self._config("refresh_stale_metrics") in ("True", "1", True),
            "refresh_closed_metrics": self._config("refresh_closed_metrics") in ("True", "1", True),
            "total_eligible": self.search_count(eligible_domain),
            "pending_count": self.search_count(pending_domain),
            "success_count": self.search_count(expression.AND([eligible_domain, [("metrics_sync_status", "=", "success")]])),
            "failed_count": self.search_count(expression.AND([eligible_domain, [("metrics_sync_status", "=", "failed")]])),
            "not_available_count": self.search_count(expression.AND([eligible_domain, [("metrics_sync_status", "=", "not_available")]])),
        }
        if values["pending_count"] == 0 and state.status == "running":
            values.update({"status": "completed", "completed_at": fields.Datetime.now()})
        state.write(values)
        return state

    @api.model
    def start_full_metrics_refresh(self):
        if self._config("sync_metrics") not in ("True", "1", True):
            raise UserError(_("Synchronize Ticket Metrics is disabled."))
        domain = self._metrics_eligible_domain()
        tickets = self.search(domain)
        tickets.write({
            "metrics_sync_status": "pending",
            "metrics_sync_attempts": 0,
            "metrics_next_retry": False,
            "metrics_error": False,
        })
        state = self._get_or_create_metrics_sync_state()
        state.write({
            "status": "running",
            "completed_at": False,
            "last_error": False,
        })
        self._update_metrics_sync_state(state)
        self.env["it.zoho.metrics.sync.history"].sudo().create({
            "name": _("Zoho Metrics Full Refresh Queued"),
            "trigger": "full_refresh",
            "completed_at": fields.Datetime.now(),
            "status": "success",
            "selected_count": len(tickets),
            "processed_count": 0,
            "pending_after": len(tickets),
            "company_id": self.env.company.id,
        })
        cron = self.env.ref(
            "isw_it_dashboard_zoho.ir_cron_zoho_metrics_batch_sync",
            raise_if_not_found=False,
        )
        if cron:
            cron.sudo().write({"active": True, "nextcall": fields.Datetime.now()})
        return len(tickets)

    @api.model
    def sync_metrics_batch(self, batch_size=None, raise_on_error=False, trigger="cron"):
        empty = {"processed": 0, "success": 0, "failed": 0, "not_available": 0, "skipped": 0}
        if self._config("sync_metrics") not in ("True", "1", True):
            return empty

        state = self._get_or_create_metrics_sync_state()
        self._update_metrics_sync_state(state)
        if trigger == "cron" and state.status == "paused":
            return empty

        if batch_size is None:
            batch_size = int(self._config("metrics_batch_size", state.batch_size or 100) or 100)
        batch_size = max(1, min(int(batch_size), 500))
        time_budget = max(30, min(int(self._config("metrics_time_budget_seconds", state.time_budget_seconds or 240) or 240), 1800))

        pending_before = self.search_count(self._pending_metrics_domain())
        tickets = self.search(
            self._pending_metrics_domain(),
            order="metrics_sync_attempts asc, modified_time desc, id",
            limit=batch_size,
        )
        if len(tickets) < batch_size:
            stale = self.search(
                expression.AND([self._stale_metrics_domain(state), [("id", "not in", tickets.ids)]]),
                order="metrics_last_sync asc nulls first, modified_time desc, id",
                limit=batch_size - len(tickets),
            )
            tickets |= stale

        history = self.env["it.zoho.metrics.sync.history"].sudo().create({
            "name": _("Zoho Metrics Batch"),
            "trigger": trigger if trigger in ("cron", "manual", "full_refresh") else "cron",
            "requested_batch_size": batch_size,
            "selected_count": len(tickets),
            "pending_before": pending_before,
            "company_id": self.env.company.id,
        })
        started = time.monotonic()
        result = dict(empty)
        state.write({"status": "running", "last_run_at": fields.Datetime.now(), "last_error": False})
        batch_error = False

        try:
            for ticket in tickets:
                if time.monotonic() - started >= time_budget:
                    result["skipped"] += len(tickets) - result["processed"]
                    break
                result["processed"] += 1
                try:
                    ok = ticket._sync_metrics(raise_on_error=False)
                    if ok:
                        result["success"] += 1
                    elif ticket.metrics_sync_status == "not_available":
                        result["not_available"] += 1
                    else:
                        result["failed"] += 1
                except Exception as exc:
                    result["failed"] += 1
                    batch_error = str(exc.args[0] if exc.args else exc)[:4000]
                    _logger.exception("Unexpected metric batch failure for %s", ticket.zoho_ticket_id)

            pending_after = self.search_count(self._pending_metrics_domain())
            duration = time.monotonic() - started
            status = "partial" if result["failed"] or result["skipped"] else "success"
            history.write({
                "completed_at": fields.Datetime.now(),
                "status": status,
                "processed_count": result["processed"],
                "success_count": result["success"],
                "failed_count": result["failed"],
                "not_available_count": result["not_available"],
                "skipped_count": result["skipped"],
                "pending_after": pending_after,
                "duration_seconds": duration,
                "error_message": batch_error or False,
            })
            state.write({
                "last_batch_selected": len(tickets),
                "last_batch_processed": result["processed"],
                "last_batch_success": result["success"],
                "last_batch_failed": result["failed"],
                "last_batch_not_available": result["not_available"],
                "last_error": batch_error or False,
            })
            self._update_metrics_sync_state(state)
            return result
        except Exception as exc:
            safe_error = str(exc.args[0] if exc.args else exc)[:4000]
            history.write({
                "completed_at": fields.Datetime.now(),
                "status": "failed",
                "processed_count": result["processed"],
                "success_count": result["success"],
                "failed_count": result["failed"],
                "not_available_count": result["not_available"],
                "skipped_count": result["skipped"],
                "duration_seconds": time.monotonic() - started,
                "error_message": safe_error,
            })
            state.write({"status": "failed", "last_error": safe_error})
            _logger.exception("Zoho metrics batch synchronization failed")
            if raise_on_error:
                raise
            return result

    @api.model
    def sync_tickets(self, raise_on_error=False):
        """Backward-compatible method: process one ticket batch only."""
        counts = self.sync_ticket_batch(raise_on_error=raise_on_error)
        return {
            **counts,
            "metrics_synced": 0,
            "metrics_failed": 0,
        }

    @api.model
    def cron_sync_ticket_batch(self):
        return self.sync_ticket_batch(raise_on_error=False)

    @api.model
    def cron_sync_metrics_batch(self):
        return self.sync_metrics_batch(raise_on_error=False, trigger="cron")

    @api.model
    def cron_sync_tickets(self):
        return self.cron_sync_ticket_batch()


class ITZohoTicketStageMetric(models.Model):
    _name = "it.zoho.ticket.stage.metric"
    _description = "Zoho Ticket Status Handling Metric"
    _order = "ticket_id, id"

    ticket_id = fields.Many2one(
        "it.zoho.ticket", required=True, ondelete="cascade", index=True
    )
    status = fields.Char(required=True, index=True)
    handled_time_seconds = fields.Integer(string="Handled Time (Seconds)")
    handled_time_minutes = fields.Float(
        string="Handled Time (Minutes)", compute="_compute_handled_time_minutes", store=True
    )

    @api.depends("handled_time_seconds")
    def _compute_handled_time_minutes(self):
        for record in self:
            record.handled_time_minutes = (record.handled_time_seconds or 0) / 60.0


class ITZohoTicketAgentMetric(models.Model):
    _name = "it.zoho.ticket.agent.metric"
    _description = "Zoho Ticket Agent Handling Metric"
    _order = "ticket_id, handling_time_seconds desc, id"

    ticket_id = fields.Many2one(
        "it.zoho.ticket", required=True, ondelete="cascade", index=True
    )
    zoho_agent_id = fields.Char(string="Zoho Agent ID", index=True)
    agent_name = fields.Char(required=True, index=True)
    handling_time_seconds = fields.Integer(string="Handling Time (Seconds)")
    handling_time_minutes = fields.Float(
        string="Handling Time (Minutes)", compute="_compute_handling_time_minutes", store=True
    )

    @api.depends("handling_time_seconds")
    def _compute_handling_time_minutes(self):
        for record in self:
            record.handling_time_minutes = (record.handling_time_seconds or 0) / 60.0
