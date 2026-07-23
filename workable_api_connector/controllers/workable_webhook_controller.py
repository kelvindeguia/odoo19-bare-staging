# -*- coding: utf-8 -*-

import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class WorkableWebhookController(http.Controller):

    def _json_response(self, payload, status=200):
        return request.make_response(
            json.dumps(payload),
            headers=[("Content-Type", "application/json")],
            status=status,
        )

    def _is_valid_secret(self):
        ICP = request.env["ir.config_parameter"].sudo()
        configured_secret = ICP.get_param("workable.webhook_secret")
        if not configured_secret:
            # Allow testing before secret is configured, but production should set a secret.
            return True

        incoming_secret = (
            request.httprequest.headers.get("X-Workable-Webhook-Secret")
            or request.httprequest.headers.get("X-Webhook-Secret")
            or request.httprequest.headers.get("X-Workable-Signature")
            or request.params.get("secret")
        )
        return incoming_secret == configured_secret

    @http.route("/workable/webhook", type="http", auth="public", methods=["POST"], csrf=False)
    def workable_webhook(self, **kwargs):
        if not self._is_valid_secret():
            return self._json_response({"ok": False, "error": "Invalid webhook secret"}, status=401)

        raw_body = request.httprequest.get_data(as_text=True) or "{}"
        try:
            payload = json.loads(raw_body)
        except Exception:
            payload = dict(kwargs or {})

        headers = {
            key: value
            for key, value in request.httprequest.headers.items()
            if key.lower() not in {"authorization", "cookie"}
        }
        source_ip = request.httprequest.headers.get("X-Forwarded-For") or request.httprequest.remote_addr

        try:
            event = request.env["workable.webhook.event"].sudo().create_from_payload(
                payload,
                headers=headers,
                source_ip=source_ip,
            )

            auto_process = request.env["ir.config_parameter"].sudo().get_param("workable.webhook_auto_process")
            if auto_process in ("1", "True", "true", True):
                # Keep the HTTP response quick where possible. For heavy production traffic,
                # disable this and use the cron queue only.
                event.sudo().action_process_event()

            return self._json_response({"ok": True, "event_id": event.id, "state": event.state})
        except Exception as exc:
            _logger.exception("Failed receiving Workable webhook")
            return self._json_response({"ok": False, "error": str(exc)}, status=500)
