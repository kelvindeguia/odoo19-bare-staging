from odoo import _, fields, models


class ITZohoMetricsSyncState(models.Model):
    _name = "it.zoho.metrics.sync.state"
    _description = "Zoho Desk Metrics Synchronization State"
    _order = "company_id, id"

    name = fields.Char(required=True, default="Zoho Desk Metrics Sync")
    status = fields.Selection(
        [
            ("idle", "Idle"),
            ("running", "Running"),
            ("paused", "Paused"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        default="idle",
        required=True,
        index=True,
    )
    batch_size = fields.Integer(default=100, required=True)
    time_budget_seconds = fields.Integer(default=240, required=True)
    stale_after_hours = fields.Integer(default=6, required=True)
    refresh_stale_metrics = fields.Boolean(default=True)
    refresh_closed_metrics = fields.Boolean(default=False)
    total_eligible = fields.Integer(readonly=True)
    pending_count = fields.Integer(readonly=True)
    success_count = fields.Integer(readonly=True)
    failed_count = fields.Integer(readonly=True)
    not_available_count = fields.Integer(readonly=True)
    last_batch_selected = fields.Integer(readonly=True)
    last_batch_processed = fields.Integer(readonly=True)
    last_batch_success = fields.Integer(readonly=True)
    last_batch_failed = fields.Integer(readonly=True)
    last_batch_not_available = fields.Integer(readonly=True)
    last_run_at = fields.Datetime(readonly=True)
    completed_at = fields.Datetime(readonly=True)
    last_error = fields.Text(readonly=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )

    _unique_company = models.Constraint(
        "UNIQUE(company_id)",
        "Only one Zoho metrics synchronization state is allowed per company.",
    )

    def action_start_full_refresh(self):
        self.ensure_one()
        count = self.env["it.zoho.ticket"].sudo().start_full_metrics_refresh()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Zoho Metrics Refresh"),
                "message": _("Queued %(count)s ticket(s). The metrics cron will continue automatically in batches.") % {"count": count},
                "type": "success",
                "sticky": False,
            },
        }

    def action_pause(self):
        self.write({"status": "paused"})

    def action_resume(self):
        self.write({"status": "running", "last_error": False})
        cron = self.env.ref(
            "isw_it_dashboard_zoho.ir_cron_zoho_metrics_batch_sync",
            raise_if_not_found=False,
        )
        if cron:
            cron.sudo().write({"active": True, "nextcall": fields.Datetime.now()})

    def action_refresh_counts(self):
        for state in self:
            self.env["it.zoho.ticket"].sudo()._update_metrics_sync_state(state)
