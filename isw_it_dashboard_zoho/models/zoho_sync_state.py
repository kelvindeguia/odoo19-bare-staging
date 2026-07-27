from odoo import _, fields, models


class ITZohoSyncState(models.Model):
    _name = "it.zoho.sync.state"
    _description = "Zoho Desk Synchronization State"
    _order = "last_attempt_at asc, id"

    name = fields.Char(required=True, default="Zoho Desk Ticket Sync")
    department_id = fields.Char(string="Zoho Department ID", index=True)
    next_offset = fields.Integer(default=0, required=True)
    batch_size = fields.Integer(default=50, required=True)
    initial_sync_completed = fields.Boolean(default=False, readonly=True)
    last_successful_sync = fields.Datetime(readonly=True)
    last_attempt_at = fields.Datetime(readonly=True, index=True)
    current_run_started = fields.Datetime(readonly=True)
    last_received_count = fields.Integer(readonly=True)
    last_error = fields.Text(readonly=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)

    _unique_department_company = models.Constraint(
        "UNIQUE(department_id, company_id)",
        "Only one active synchronization state is allowed per Zoho department and company.",
    )

    def action_reset_offset(self):
        self.write({
            "next_offset": 0,
            "initial_sync_completed": False,
            "last_error": False,
            "current_run_started": False,
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Zoho Sync State"), "message": _("The ticket offset was reset to zero."), "type": "success"},
        }
