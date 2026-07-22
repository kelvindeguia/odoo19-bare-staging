import hashlib
import hmac
import json
import logging

from werkzeug.exceptions import BadRequest, Forbidden, NotFound

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class WorkableHealthWebhookController(http.Controller):

    @http.route(
        "/workable/health/webhook/<string:webhook_key>",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def workable_health_webhook(self, webhook_key, **kwargs):
        account = request.env["workable.api.account"].sudo().search(
            [("webhook_key", "=", webhook_key), ("active", "=", True)],
            limit=1,
        )
        if not account:
            raise NotFound("Unknown Workable webhook endpoint")

        raw_body = request.httprequest.get_data(cache=True) or b""
        received_signature = (
            request.httprequest.headers.get("X-Workable-Signature") or ""
        ).strip()
        event_type = (
            request.httprequest.headers.get("X-Workable-Event") or ""
        ).strip()

        try:
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {}

        event_type = event_type or account._extract_event_type(payload)
        signature_valid = account._validate_webhook_signature(
            raw_body, received_signature
        )

        event = request.env["workable.webhook.event"].sudo().create(
            {
                "account_id": account.id,
                "received_at": fields.Datetime.now(),
                "event_type": event_type or "unknown",
                "signature_valid": signature_valid,
                "remote_address": request.httprequest.remote_addr,
                "request_headers": json.dumps(
                    dict(request.httprequest.headers), indent=2, default=str
                ),
                "payload": raw_body.decode("utf-8", errors="replace"),
                "processing_status": "received" if signature_valid else "rejected",
                "message": (
                    "Webhook received and signature validated."
                    if signature_valid
                    else "Webhook rejected because the signature is invalid or missing."
                ),
            }
        )

        if not signature_valid:
            account.sudo().write(
                {
                    "last_invalid_webhook_at": fields.Datetime.now(),
                    "invalid_webhook_count": account.invalid_webhook_count + 1,
                }
            )
            _logger.warning(
                "Rejected Workable webhook for account %s; event record %s",
                account.display_name,
                event.id,
            )
            raise Forbidden("Invalid Workable signature")

        now = fields.Datetime.now()
        account.sudo().write(
            {
                "last_webhook_at": now,
                "valid_webhook_count": account.valid_webhook_count + 1,
            }
        )

        subscription = request.env["workable.api.subscription"].sudo().search(
            [
                ("account_id", "=", account.id),
                ("event_type", "=", event_type),
                ("active", "=", True),
            ],
            limit=1,
        )
        if subscription:
            subscription.write(
                {
                    "last_webhook_received": now,
                    "last_webhook_signature_valid": True,
                }
            )
            event.subscription_id = subscription.id

        event.processing_status = "processed"
        return request.make_json_response({"ok": True}, status=200)
