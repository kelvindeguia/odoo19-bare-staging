from odoo import models, fields,api
from datetime import date
from odoo.exceptions import UserError

class InfraDashboard(models.Model):
    _name = 'it.infra.dashboard'
    _description = 'IT Infra Dashboard'
    _inherit = ['it.dashboard.weekly.mixin'] 

    name = fields.Char(default=lambda self: f"Infra Dashboard Input - {date.today()}")

    _rec_name = 'name'

    infra_ongoing_projects = fields.Integer(string="Ongoing Projects")
    network_uptime = fields.Char(string="Network Uptime")
    server_uptime = fields.Char(string="Odoo System Uptime")
    security_breach = fields.Char(string="Security Breach")
    telephony_uptime = fields.Char(string="Telephony Uptime")
    internet_uptime = fields.Char(string="Internet Uptime")

    infra_kpis_attainment = fields.Text(string="Major KPIs and Attainment")
    infra_key_wins = fields.Text(string="Key Wins for the Month")
    infra_challenges = fields.Text(string="Challenges")
    infra_help_needed = fields.Text(string="Help Needed")

    def action_open_dashboard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "infra_dashboard_live",  
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
