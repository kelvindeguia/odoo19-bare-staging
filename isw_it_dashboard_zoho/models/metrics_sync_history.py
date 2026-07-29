from odoo import fields, models


class ITZohoMetricsSyncHistory(models.Model):
    _name = "it.zoho.metrics.sync.history"
    _description = "Zoho Desk Metrics Synchronization History"
    _order = "started_at desc, id desc"

    name = fields.Char(required=True, default="Zoho Metrics Batch")
    trigger = fields.Selection(
        [("cron", "Scheduled Action"), ("manual", "Manual Batch"), ("full_refresh", "Full Refresh")],
        default="cron",
        required=True,
        index=True,
    )
    started_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    completed_at = fields.Datetime()
    status = fields.Selection(
        [("running", "Running"), ("success", "Success"), ("partial", "Partial"), ("failed", "Failed")],
        default="running",
        required=True,
        index=True,
    )
    requested_batch_size = fields.Integer()
    selected_count = fields.Integer()
    processed_count = fields.Integer()
    success_count = fields.Integer()
    failed_count = fields.Integer()
    not_available_count = fields.Integer()
    skipped_count = fields.Integer()
    pending_before = fields.Integer()
    pending_after = fields.Integer()
    duration_seconds = fields.Float(digits=(16, 2))
    error_message = fields.Text()
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
