import json
from odoo import http
from odoo.http import request, Response

class ZohoDeskWebhookController(http.Controller):
    @http.route("/it-dashboard/zoho/webhook", type="http", auth="public", methods=["POST"], csrf=False)
    def zoho_webhook(self, **kwargs):
        configured = request.env["ir.config_parameter"].sudo().get_param("isw_it_dashboard_zoho.webhook_secret")
        supplied = request.httprequest.headers.get("X-Webhook-Secret") or request.params.get("secret")
        if not configured or supplied != configured:
            return Response("Unauthorized", status=401)
        try:
            payload = request.httprequest.get_json(silent=True) or {}
            ticket_id = payload.get("ticketId") or payload.get("id") or (payload.get("payload") or {}).get("ticketId")
            event_type = payload.get("eventType") or payload.get("event") or "ticket_update"
            request.env["it.zoho.webhook.event"].sudo().create({"event_type": event_type, "zoho_ticket_id": str(ticket_id or ""), "payload": json.dumps(payload, ensure_ascii=False)})
            return Response("Accepted", status=202)
        except Exception as exc:
            return Response(str(exc), status=400)
