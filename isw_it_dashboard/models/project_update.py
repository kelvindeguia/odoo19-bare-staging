from odoo import fields, models


class ITProjectUpdate(models.Model):
    _name = "it.project.update"
    _description = "IT Project Monthly Update"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "period_id desc, id desc"

    name = fields.Char(required=True, tracking=True)
    period_id = fields.Many2one("it.dashboard.period", required=True, ondelete="cascade", index=True)
    project_id = fields.Many2one("project.project")
    owner_id = fields.Many2one("res.users", default=lambda self: self.env.user)
    status = fields.Selection([
        ("projected", "Projected"),
        ("ongoing", "Ongoing"),
        ("on_hold", "On Hold"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ], default="ongoing", required=True, tracking=True, index=True)
    progress_percentage = fields.Float(default=0.0)
    target_date = fields.Date()
    achievement_summary = fields.Html()
    risk_level = fields.Selection([("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")], default="low")
    remarks = fields.Text()

    _progress_range = models.Constraint(
        "CHECK(progress_percentage >= 0 AND progress_percentage <= 100)",
        "Project progress must be between 0 and 100.",
    )
