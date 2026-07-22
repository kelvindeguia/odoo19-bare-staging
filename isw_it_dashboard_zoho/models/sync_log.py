from odoo import fields, models

class ITIntegrationSyncLog(models.Model):
    _name = "it.integration.sync.log"
    _description = "IT Integration Sync Log"
    _order = "started_at desc"

    name = fields.Char(required=True, default="Zoho Desk Ticket Sync")
    integration = fields.Selection([("zoho_desk", "Zoho Desk")], default="zoho_desk", required=True)
    started_at = fields.Datetime(default=fields.Datetime.now, required=True)
    completed_at = fields.Datetime()
    status = fields.Selection([("running", "Running"), ("success", "Success"), ("partial", "Partial"), ("failed", "Failed")], default="running", required=True)
    records_received = fields.Integer()
    records_created = fields.Integer()
    records_updated = fields.Integer()
    records_failed = fields.Integer()
    error_message = fields.Text()
