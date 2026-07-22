import json
import logging
from datetime import timedelta
import requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ITZohoTicket(models.Model):
    _name = "it.zoho.ticket"
    _description = "Zoho Desk Ticket"
    _order = "created_time desc"

    zoho_ticket_id = fields.Char(required=True, index=True)
    ticket_number = fields.Char(index=True)
    subject = fields.Char()
    department_id_external = fields.Char(index=True)
    department_name = fields.Char()
    channel = fields.Char(index=True)
    status = fields.Char(index=True)
    priority = fields.Char(index=True)
    category = fields.Char(index=True)
    subcategory = fields.Char()
    created_time = fields.Datetime(index=True)
    modified_time = fields.Datetime(index=True)
    due_date = fields.Datetime()
    first_response_time = fields.Datetime()
    closed_time = fields.Datetime(index=True)
    resolution_time_minutes = fields.Float()
    first_response_minutes = fields.Float()
    response_time_minutes = fields.Float()
    sla_violated = fields.Boolean(index=True)
    customer_rating = fields.Float()
    assignee_id_external = fields.Char()
    assignee_name = fields.Char()
    account_name = fields.Char()
    contact_name = fields.Char()
    raw_payload = fields.Text()
    last_sync_date = fields.Datetime(default=fields.Datetime.now, index=True)

    _unique_zoho_ticket = models.Constraint("UNIQUE(zoho_ticket_id)", "The Zoho ticket ID must be unique.")

    @api.model
    def _config(self, key, default=False):
        return self.env["ir.config_parameter"].sudo().get_param(f"isw_it_dashboard_zoho.{key}", default)

    @api.model
    def _get_access_token(self):
        params = {
            "refresh_token": self._config("refresh_token"),
            "client_id": self._config("client_id"),
            "client_secret": self._config("client_secret"),
            "grant_type": "refresh_token",
        }
        if not all(params.values()):
            raise UserError(_("Complete the Zoho Desk OAuth configuration first."))
        response = requests.post(f"{self._config('accounts_url', 'https://accounts.zoho.com').rstrip('/')}/oauth/v2/token", params=params, timeout=30)
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            raise UserError(_("Zoho did not return an access token."))
        return token

    @api.model
    def _headers(self):
        return {"Authorization": f"Zoho-oauthtoken {self._get_access_token()}", "orgId": self._config("org_id"), "Content-Type": "application/json"}

    @api.model
    def _parse_datetime(self, value):
        if not value:
            return False
        try:
            return fields.Datetime.to_datetime(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return False

    @api.model
    def _ticket_values(self, data):
        assignee = data.get("assignee") or {}
        contact = data.get("contact") or {}
        account = data.get("account") or {}
        return {
            "zoho_ticket_id": str(data.get("id")),
            "ticket_number": data.get("ticketNumber"),
            "subject": data.get("subject"),
            "department_id_external": str(data.get("departmentId") or ""),
            "department_name": (data.get("department") or {}).get("name") if isinstance(data.get("department"), dict) else data.get("departmentName"),
            "channel": data.get("channel"), "status": data.get("status"), "priority": data.get("priority"),
            "category": data.get("category"), "subcategory": data.get("subCategory"),
            "created_time": self._parse_datetime(data.get("createdTime")),
            "modified_time": self._parse_datetime(data.get("modifiedTime")),
            "due_date": self._parse_datetime(data.get("dueDate")),
            "first_response_time": self._parse_datetime(data.get("firstResponseTime")),
            "closed_time": self._parse_datetime(data.get("closedTime")),
            "resolution_time_minutes": float(data.get("resolutionTime") or 0),
            "first_response_minutes": float(data.get("firstResponseTimeInMillis") or 0) / 60000 if data.get("firstResponseTimeInMillis") else 0,
            "response_time_minutes": float(data.get("responseTime") or 0),
            "sla_violated": bool(data.get("isOverDue") or data.get("slaViolated")),
            "customer_rating": float(data.get("customerHappiness", {}).get("rating") or data.get("rating") or 0) if isinstance(data.get("customerHappiness", {}), dict) else 0,
            "assignee_id_external": str(assignee.get("id") or data.get("assigneeId") or ""),
            "assignee_name": assignee.get("name") or data.get("assigneeName"),
            "account_name": account.get("accountName") or data.get("accountName"),
            "contact_name": contact.get("lastName") or contact.get("firstName") or data.get("contactName"),
            "raw_payload": json.dumps(data, ensure_ascii=False), "last_sync_date": fields.Datetime.now(),
        }

    @api.model
    def _upsert_ticket(self, data):
        vals = self._ticket_values(data)
        if not vals["zoho_ticket_id"] or vals["zoho_ticket_id"] == "None":
            return "failed"
        rec = self.search([("zoho_ticket_id", "=", vals["zoho_ticket_id"])], limit=1)
        if rec:
            rec.write(vals); return "updated"
        self.create(vals); return "created"

    @api.model
    def _sync_single_ticket(self, ticket_id):
        response = requests.get(f"{self._config('api_base', 'https://desk.zoho.com/api/v1').rstrip('/')}/tickets/{ticket_id}", headers=self._headers(), timeout=30)
        response.raise_for_status()
        return self._upsert_ticket(response.json())

    @api.model
    def cron_sync_tickets(self):
        if self._config("enabled") not in ("True", "1", True):
            return
        log = self.env["it.integration.sync.log"].sudo().create({})
        counts = {"received": 0, "created": 0, "updated": 0, "failed": 0}
        try:
            api_base = self._config("api_base", "https://desk.zoho.com/api/v1").rstrip("/")
            modified_since = fields.Datetime.now() - timedelta(days=2)
            params = {"from": 0, "limit": 100, "sortBy": "modifiedTime"}
            dept_ids = [x.strip() for x in (self._config("department_ids") or "").split(",") if x.strip()]
            if dept_ids: params["departmentId"] = dept_ids[0]
            while True:
                response = requests.get(f"{api_base}/tickets", headers=self._headers(), params=params, timeout=60)
                response.raise_for_status()
                payload = response.json()
                tickets = payload.get("data", payload if isinstance(payload, list) else [])
                if not tickets: break
                for data in tickets:
                    modified = self._parse_datetime(data.get("modifiedTime"))
                    if modified and modified < modified_since: continue
                    counts["received"] += 1
                    try: counts[self._upsert_ticket(data)] += 1
                    except Exception: counts["failed"] += 1; _logger.exception("Zoho ticket sync failed")
                if len(tickets) < params["limit"]: break
                params["from"] += params["limit"]
            log.write({"completed_at": fields.Datetime.now(), "status": "partial" if counts["failed"] else "success", "records_received": counts["received"], "records_created": counts["created"], "records_updated": counts["updated"], "records_failed": counts["failed"]})
        except Exception as exc:
            log.write({"completed_at": fields.Datetime.now(), "status": "failed", "error_message": str(exc)})
            _logger.exception("Zoho Desk synchronization failed")
