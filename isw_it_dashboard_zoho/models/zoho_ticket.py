import json
import logging
from datetime import datetime, timedelta, timezone

import requests

from odoo import _, api, fields, models
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
    average_response_time_seconds = fields.Integer(string="Average Response Time (Seconds)", index=True)
    resolution_time_seconds = fields.Integer(string="Resolution Time (Seconds)", index=True)
    first_response_minutes = fields.Float(string="First Response Time (Minutes)", compute="_compute_metric_minutes", store=True)
    response_time_minutes = fields.Float(string="Average Response Time (Minutes)", compute="_compute_metric_minutes", store=True)
    resolution_time_minutes = fields.Float(string="Resolution Time (Minutes)", compute="_compute_metric_minutes", store=True)
    calendar_resolution_time_minutes = fields.Float(string="Calendar Resolution Time (Minutes)", readonly=True)
    response_count = fields.Integer(string="Agent Response Count")
    sla_violated = fields.Boolean(index=True)
    first_response_sla_violated = fields.Boolean(string="First Response SLA Violated", index=True)
    resolution_sla_violated = fields.Boolean(string="Resolution SLA Violated", index=True)
    customer_rating = fields.Float()

    metrics_sync_status = fields.Selection(
        [("pending", "Pending"), ("success", "Success"), ("failed", "Failed"), ("not_available", "Not Available")],
        default="pending",
        index=True,
        readonly=True,
    )
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
        "average_response_time_seconds",
        "resolution_time_seconds",
    )
    def _compute_metric_minutes(self):
        for record in self:
            record.first_response_minutes = (record.first_response_time_seconds or 0) / 60.0
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

        Supports numbers, millisecond fields, numeric strings, HH:MM, and HH:MM:SS.
        """
        if value in (None, False, ""):
            return 0
        if isinstance(value, (int, float)):
            seconds = float(value) / 1000.0 if assume_milliseconds else float(value)
            return max(int(round(seconds)), 0)

        text = str(value).strip()
        try:
            numeric = float(text)
            seconds = numeric / 1000.0 if assume_milliseconds else numeric
            return max(int(round(seconds)), 0)
        except ValueError:
            pass

        parts = text.split(":")
        try:
            if len(parts) == 3:
                hours, minutes, seconds = parts
                return max(int(float(hours) * 3600 + float(minutes) * 60 + float(seconds)), 0)
            if len(parts) == 2:
                hours, minutes = parts
                return max(int(float(hours) * 3600 + float(minutes) * 60), 0)
        except ValueError:
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
        # Some Zoho responses wrap metrics in data; others return the object directly.
        metrics = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
        metrics = metrics if isinstance(metrics, dict) else {}

        first_response_seconds = self._metric_value(
            metrics,
            (
                "firstResponseTimeInSeconds",
                "firstResponseTime",
                "firstResponseDuration",
                "firstResponseTimeTaken",
            ),
            ("firstResponseTimeInMillis", "firstResponseTimeMillis"),
        )
        average_response_seconds = self._metric_value(
            metrics,
            (
                "averageResponseTimeInSeconds",
                "averageResponseTime",
                "responseTimeInSeconds",
                "responseTime",
                "responseDuration",
            ),
            ("averageResponseTimeInMillis", "responseTimeInMillis", "responseTimeMillis"),
        )
        resolution_seconds = self._metric_value(
            metrics,
            (
                "resolutionTimeInSeconds",
                "resolutionTime",
                "resolutionDuration",
                "resolutionTimeTaken",
            ),
            ("resolutionTimeInMillis", "resolutionTimeMillis"),
        )

        first_response_at = (
            metrics.get("firstResponseAt")
            or metrics.get("firstResponseTimeStamp")
            or metrics.get("firstRespondedTime")
        )

        return {
            "first_response_time_seconds": first_response_seconds,
            "average_response_time_seconds": average_response_seconds,
            "resolution_time_seconds": resolution_seconds,
            "response_count": int(metrics.get("responseCount") or metrics.get("agentResponseCount") or 0),
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

    @api.model
    def _upsert_ticket(self, data):
        vals = self._ticket_values(data)
        if not vals["zoho_ticket_id"]:
            return False, "failed"
        record = self.search([("zoho_ticket_id", "=", vals["zoho_ticket_id"])], limit=1)
        if record:
            record.write(vals)
            return record, "updated"
        return self.create(vals), "created"

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
        try:
            response = self._request("GET", endpoint, timeout=30, allow_not_found=True)
            if response.status_code in (404, 405):
                error = _("The configured Zoho metrics endpoint is not available for this ticket or account.")
                self.write({
                    "metrics_sync_status": "not_available",
                    "metrics_last_sync": fields.Datetime.now(),
                    "metrics_error": error,
                })
                if raise_on_error:
                    raise UserError(error)
                return False

            payload = response.json()
            self.write(self._metrics_values(payload))
            return True
        except Exception as exc:
            error = exc.args[0] if exc.args else str(exc)
            self.write({
                "metrics_sync_status": "failed",
                "metrics_last_sync": fields.Datetime.now(),
                "metrics_error": str(error),
            })
            _logger.exception("Zoho metrics synchronization failed for ticket %s", self.zoho_ticket_id)
            if raise_on_error:
                raise
            return False

    @api.model
    def _sync_single_ticket(self, ticket_id):
        response = self._request("GET", f"tickets/{ticket_id}", timeout=30)
        record, outcome = self._upsert_ticket(response.json())
        if record and self._config("sync_metrics") in ("True", "1", True):
            record._sync_metrics(raise_on_error=False)
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
    def sync_tickets(self, raise_on_error=False):
        if self._config("enabled") not in ("True", "1", True):
            if raise_on_error:
                raise UserError(_("Zoho Desk synchronization is disabled."))
            return {"received": 0, "created": 0, "updated": 0, "failed": 0, "metrics_synced": 0, "metrics_failed": 0}

        log = self.env["it.integration.sync.log"].sudo().create({})
        counts = {"received": 0, "created": 0, "updated": 0, "failed": 0, "metrics_synced": 0, "metrics_failed": 0}
        try:
            try:
                lookback_days = max(int(self._config("sync_lookback_days", 7) or 7), 1)
            except (TypeError, ValueError):
                lookback_days = 7
            modified_since = fields.Datetime.now() - timedelta(days=lookback_days)
            department_ids = [value.strip() for value in (self._config("department_ids") or "").split(",") if value.strip()] or [False]
            sync_metrics = self._config("sync_metrics") in ("True", "1", True)
            metrics_closed_only = self._config("metrics_closed_only") in ("True", "1", True)

            for department_id in department_ids:
                offset = 0
                while True:
                    params = {"from": offset, "limit": 100, "sortBy": "modifiedTime"}
                    if department_id:
                        params["departmentId"] = department_id
                    response = self._request("GET", "tickets", params=params)
                    payload = response.json()
                    tickets = payload.get("data", []) if isinstance(payload, dict) else payload
                    if not tickets:
                        break
                    for data in tickets:
                        modified = self._parse_datetime(data.get("modifiedTime"))
                        if modified and fields.Datetime.to_datetime(modified) < modified_since:
                            continue
                        counts["received"] += 1
                        try:
                            record, outcome = self._upsert_ticket(data)
                            counts[outcome] += 1
                            should_sync_metrics = sync_metrics and record and (
                                not metrics_closed_only or (data.get("statusType") == "Closed" or data.get("status") == "Closed")
                            )
                            if should_sync_metrics:
                                if record._sync_metrics(raise_on_error=False):
                                    counts["metrics_synced"] += 1
                                else:
                                    counts["metrics_failed"] += 1
                        except Exception:
                            counts["failed"] += 1
                            _logger.exception("Zoho ticket mapping failed for ticket ID %s", data.get("id"))
                    if len(tickets) < 100:
                        break
                    offset += 100

            status = "partial" if counts["failed"] or counts["metrics_failed"] else "success"
            log.write({
                "completed_at": fields.Datetime.now(),
                "status": status,
                "records_received": counts["received"],
                "records_created": counts["created"],
                "records_updated": counts["updated"],
                "records_failed": counts["failed"] + counts["metrics_failed"],
                "error_message": _("Metrics synchronized: %(ok)s; metrics failed/unavailable: %(failed)s")
                % {"ok": counts["metrics_synced"], "failed": counts["metrics_failed"]},
            })
            self._set_config("last_sync_at", fields.Datetime.to_string(fields.Datetime.now()))
            self._set_config("last_error", "")
            return counts
        except Exception as exc:
            safe_error = exc.args[0] if exc.args else _("Unknown synchronization error")
            log.write({
                "completed_at": fields.Datetime.now(),
                "status": "failed",
                "records_received": counts["received"],
                "records_created": counts["created"],
                "records_updated": counts["updated"],
                "records_failed": counts["failed"] + counts["metrics_failed"],
                "error_message": str(safe_error),
            })
            self._set_config("connection_status", "error")
            self._set_config("last_error", str(safe_error))
            _logger.exception("Zoho Desk synchronization failed")
            if raise_on_error:
                raise
            return counts

    @api.model
    def cron_sync_tickets(self):
        return self.sync_tickets(raise_on_error=False)
