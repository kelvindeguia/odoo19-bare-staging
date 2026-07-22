from odoo import fields, models


class WorkableHealthLog(models.Model):
    _name = "workable.health.log"
    _description = "Workable Health Check Log"
    _order = "check_date desc, id desc"

    check_date = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    account_id = fields.Many2one(
        "workable.api.account", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="account_id.company_id", store=True)
    subscription_id = fields.Many2one(
        "workable.api.subscription", ondelete="set null", index=True
    )
    check_type = fields.Selection(
        [
            ("connection", "Connection"),
            ("subscriptions", "Subscriptions"),
            ("register", "Register"),
            ("unregister", "Unregister"),
            ("webhook", "Webhook"),
            ("full", "Full Health Check"),
        ],
        required=True,
        default="full",
        index=True,
    )
    status = fields.Selection(
        [("success", "Success"), ("warning", "Warning"), ("error", "Error")],
        required=True,
        index=True,
    )
    http_status = fields.Integer()
    response_time_ms = fields.Integer()
    message = fields.Text(required=True)
    response_payload = fields.Text()
