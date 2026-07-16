from odoo import models, fields, api
from datetime import date
from odoo.exceptions import UserError

class ManagementDashboard(models.Model):
    _name = 'it.management.dashboard'
    _description = 'IT Management Dashboard'
    _inherit = ['it.dashboard.weekly.mixin'] 

    name = fields.Char(default=lambda self: f"Management Dashboard Input - {date.today()}")

    _rec_name = 'name'

    overall_it_health_rating = fields.Selection([
        ('weak', '🔴 Weak'),
        ('strong', '🟢 Strong'),
        ('very strong', '🟢 Very Strong'),
    ], string="Status", default='')
    happiness_satisfaction_rating= fields.Char(string="Happiness Satisfaction Rating")

    def action_open_dashboard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "management_dashboard_live",  
            "target": "current",
            "context": {
                "active_id": self.id,
                "view_mode": "readonly",
            },
        }
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            summary_start = vals.get("summary_start")
            summary_end = vals.get("summary_end")

            if summary_start and summary_end:
                existing = self.search([
                    ("create_uid", "=", self.env.user.id),
                    ("summary_start", "=", summary_start),
                    ("summary_end", "=", summary_end),
                ], limit=1)

                if existing:
                    raise UserError(
                        "You have already submitted a dashboard entry for this "
                        "reporting week. Please edit your existing record instead."
                    )

        records = super().create(vals_list)
        records._sync_executive_summary()

        return records

    def write(self, vals):
        for rec in self:
            is_owner = rec.create_uid.id == self.env.user.id
            is_admin = self.env.user.has_group("base.group_system")

            if not (is_owner or is_admin):
                raise UserError(
                    "Only the original creator or an administrator can edit this record."
                )

        result = super().write(vals)
        self._sync_executive_summary()

        return result

    def unlink(self):
        for rec in self:
            is_owner = rec.create_uid.id == self.env.user.id
            is_admin = self.env.user.has_group("base.group_system")

            if not (is_owner or is_admin):
                raise UserError(
                    "Only the original creator or an administrator can delete this record."
                )

        return super().unlink()
    
    def _sync_executive_summary(self):
        for rec in self:
            self.env["it.dashboard.summary.history"].sync_week(
                rec.summary_start,
                rec.summary_end,
            )
