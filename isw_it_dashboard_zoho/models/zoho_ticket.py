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
    first_response_time = fields.Datetime()
    closed_time = fields.Datetime(index=True)
    on_hold_time = fields.Datetime()
    resolution_time_minutes = fields.Float(string="Calendar Resolution Time (Minutes)")
    first_response_minutes = fields.Float()
    response_time_minutes = fields.Float()
    sla_violated = fields.Boolean(index=True)
    customer_rating = fields.Float()
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
    def _request(self, method, endpoint, params=None, timeout=60):
        api_base = (self._config("api_base", "https://desk.zoho.com/api/v1") or "").strip().rstrip("/")
        try:
            response = requests.request(
                method,
                f"{api_base}/{endpoint.lstrip('/')}",
                headers=self._headers(),
                params=params,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise UserError(_("Unable to connect to the Zoho Desk API.")) from exc

        if response.status_code == 401:
            self._get_access_token(force_refresh=True)
            response = requests.request(
                method,
                f"{api_base}/{endpoint.lstrip('/')}",
                headers=self._headers(),
                params=params,
                timeout=timeout,
            )

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
    def _as_float(self, value, divisor=1.0):
        try:
            return float(value or 0) / divisor
        except (TypeError, ValueError):
            return 0.0

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
        resolution_minutes = self._as_float(data.get("resolutionTime"))
        if not resolution_minutes and created_time and closed_time:
            created_dt = fields.Datetime.to_datetime(created_time)
            closed_dt = fields.Datetime.to_datetime(closed_time)
            resolution_minutes = max((closed_dt - created_dt).total_seconds() / 60.0, 0.0)

        contact_name = data.get("contactName")
        if not contact_name:
            contact_name = " ".join(
                part for part in (contact.get("firstName"), contact.get("lastName")) if part
            )

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
            "resolution_time_minutes": resolution_minutes,
            "first_response_minutes": self._as_float(data.get("firstResponseTimeInMillis"), 60000.0),
            "response_time_minutes": self._as_float(data.get("responseTime")),
            "sla_violated": bool(data.get("isOverDue") or data.get("slaViolated")),
            "customer_rating": self._as_float(happiness.get("rating") or data.get("rating")),
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
    def _upsert_ticket(self, data):
        vals = self._ticket_values(data)
        if not vals["zoho_ticket_id"]:
            return "failed"
        record = self.search([("zoho_ticket_id", "=", vals["zoho_ticket_id"])], limit=1)
        if record:
            record.write(vals)
            return "updated"
        self.create(vals)
        return "created"

    @api.model
    def _sync_single_ticket(self, ticket_id):
        response = self._request("GET", f"tickets/{ticket_id}", timeout=30)
        return self._upsert_ticket(response.json())

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
            return {"received": 0, "created": 0, "updated": 0, "failed": 0}

        log = self.env["it.integration.sync.log"].sudo().create({})
        counts = {"received": 0, "created": 0, "updated": 0, "failed": 0}
        try:
            try:
                lookback_days = max(int(self._config("sync_lookback_days", 7) or 7), 1)
            except (TypeError, ValueError):
                lookback_days = 7
            modified_since = fields.Datetime.now() - timedelta(days=lookback_days)
            department_ids = [
                value.strip()
                for value in (self._config("department_ids") or "").split(",")
                if value.strip()
            ] or [False]

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
                            outcome = self._upsert_ticket(data)
                            counts[outcome] += 1
                        except Exception:
                            counts["failed"] += 1
                            _logger.exception("Zoho ticket mapping failed for ticket ID %s", data.get("id"))
                    if len(tickets) < 100:
                        break
                    offset += 100

            status = "partial" if counts["failed"] else "success"
            log.write(
                {
                    "completed_at": fields.Datetime.now(),
                    "status": status,
                    "records_received": counts["received"],
                    "records_created": counts["created"],
                    "records_updated": counts["updated"],
                    "records_failed": counts["failed"],
                }
            )
            self._set_config("last_sync_at", fields.Datetime.to_string(fields.Datetime.now()))
            self._set_config("last_error", "")
            return counts
        except Exception as exc:
            safe_error = exc.args[0] if exc.args else _("Unknown synchronization error")
            log.write(
                {
                    "completed_at": fields.Datetime.now(),
                    "status": "failed",
                    "records_received": counts["received"],
                    "records_created": counts["created"],
                    "records_updated": counts["updated"],
                    "records_failed": counts["failed"],
                    "error_message": str(safe_error),
                }
            )
            self._set_config("connection_status", "error")
            self._set_config("last_error", str(safe_error))
            _logger.exception("Zoho Desk synchronization failed")
            if raise_on_error:
                raise
            return counts

    @api.model
    def cron_sync_tickets(self):
        return self.sync_tickets(raise_on_error=False)
