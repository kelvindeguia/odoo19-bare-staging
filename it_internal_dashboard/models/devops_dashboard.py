from odoo import models, fields, api
from datetime import date
from odoo.exceptions import UserError

class DevOpsDashboard(models.Model):
    _name = 'it.devops.dashboard'
    _description = 'IT DevOps Dashboard'
    _inherit = ['it.dashboard.weekly.mixin'] 

    name = fields.Char(default=lambda self: f"DevOps Dashboard Input - {date.today()}")

    _rec_name = 'name'
    
    devops_ongoing_projects = fields.Integer(string="Ongoing Projects")
    sprint_tasks_completed = fields.Char(string="Sprint Tasks Completed")
    issues_raised = fields.Integer(string="Issues Raised")
    system_uptime = fields.Char(string="Odoo System Uptime")
    cloud_servers_uptime = fields.Char(string="AWS Cloud Servers Uptime")

    devops_kpis_attainment = fields.Text(string="Major KPIs and Attainment")
    devops_key_wins = fields.Text(string="Key Wins for the Month")
    devops_challenges = fields.Text(string="Challenges")
    devops_help_needed = fields.Text(string="Help Needed")

    def action_open_dashboard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "devops_dashboard_live",  
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




