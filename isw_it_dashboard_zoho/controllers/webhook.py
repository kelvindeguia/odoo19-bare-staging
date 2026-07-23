import hmac
import json
import logging

from odoo import http
from odoo.http import Response, request

_logger = logging.getLogger(__name__)


class ZohoDeskWebhookController(http.Controller):
    @http.route(
        "/it-dashboard/zoho/webhook",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def zoho_webhook(self, **kwargs):
        configured = (
            request.env["ir.config_parameter"]
            .sudo()
            .get_param("isw_it_dashboard_zoho.webhook_secret")
            or ""
        )
        supplied = (
            request.httprequest.headers.get("X-Webhook-Secret")
            or request.params.get("secret")
            or ""
        )
        if not configured or not hmac.compare_digest(supplied, configured):
            return Response("Unauthorized", status=401)

        try:
            payload = request.httprequest.get_json(silent=True) or {}
            nested_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
            ticket_id = (
                payload.get("ticketId")
                or payload.get("id")
                or nested_payload.get("ticketId")
                or nested_payload.get("id")
            )
            event_type = payload.get("eventType") or payload.get("event") or "ticket_update"
            request.env["it.zoho.webhook.event"].sudo().create(
                {
                    "event_type": event_type,
                    "zoho_ticket_id": str(ticket_id or ""),
                    "payload": json.dumps(payload, ensure_ascii=False, indent=2),
                }
            )
            return Response("Accepted", status=202)
        except Exception:
            _logger.exception("Unable to accept Zoho Desk webhook event.")
            return Response("Invalid webhook payload", status=400)
