from odoo import fields, models


class WorkableWebhookEvent(models.Model):
    _name = "workable.webhook.event"
    _description = "Workable Webhook Event"
    _order = "received_at desc, id desc"

    received_at = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    account_id = fields.Many2one(
        "workable.api.account", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="account_id.company_id", store=True)
    subscription_id = fields.Many2one(
        "workable.api.subscription", ondelete="set null", index=True
    )
    event_type = fields.Char(required=True, index=True)
    signature_valid = fields.Boolean(index=True)
    processing_status = fields.Selection(
        [
            ("received", "Received"),
            ("processed", "Processed"),
            ("rejected", "Rejected"),
            ("error", "Error"),
        ],
        required=True,
        default="received",
        index=True,
    )
    remote_address = fields.Char()
    request_headers = fields.Text()
    payload = fields.Text()
    message = fields.Text()
