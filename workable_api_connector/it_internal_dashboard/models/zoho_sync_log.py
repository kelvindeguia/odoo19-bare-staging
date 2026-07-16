from odoo import models, fields


class ZohoSyncLog(models.Model):
    _name = "it.zoho.sync.log"
    _description = "Zoho Sync Log"
    _order = "create_date desc"

    credentials_id = fields.Many2one(
        "it.zoho.credentials",
        string="Credential Set",
        ondelete="set null",
    )
    sync_type = fields.Selection(
        [
            ("token_refresh", "Token Refresh"),
            ("dashboard_sync", "Dashboard Sync"),
            ("ticket_sync", "Ticket Sync"),
            ("manual", "Manual Trigger"),
        ],
        required=True,
    )
    status = fields.Selection(
        [
            ("success", "Success"),
            ("warning", "Warning"),
            ("error", "Error"),
        ],
        required=True,
    )
    # How many Zoho records were retrieved in this sync
    records_fetched = fields.Integer(default=0)
    # Human-readable summary of what happened
    message = fields.Text()
    # Raw JSON from Zoho, stored so you can re-parse without re-fetching
    raw_response = fields.Text()
    duration_ms = fields.Integer(string="Duration (ms)")