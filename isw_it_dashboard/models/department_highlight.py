from odoo import api, fields, models


class ITDepartmentHighlight(models.Model):
    _name = "it.department.highlight"
    _description = "IT Department Highlight"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "period_id desc, sequence, highlight_date"

    name = fields.Char(string="Title", required=True, tracking=True)
    period_id = fields.Many2one("it.dashboard.period", required=True, ondelete="cascade", index=True)
    highlight_date = fields.Date(required=True, default=fields.Date.context_today, index=True)
    category = fields.Selection([
        ("major_kpi", "Major KPI and Attainment"),
        ("key_win", "Key Win"),
        ("other", "Other Item"),
        ("challenge", "Challenge"),
        ("risk", "Risk"),
        ("action", "Action Item"),
    ], required=True, index=True)
    description = fields.Html(required=True)
    department_id = fields.Many2one("hr.department")
    owner_id = fields.Many2one("res.users", default=lambda self: self.env.user)
    include_in_monthly_report = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    state = fields.Selection([("draft", "Draft"), ("reviewed", "Reviewed"), ("published", "Published")], default="draft", tracking=True)

    def action_review(self):
        self.write({"state": "reviewed"})

    def action_publish(self):
        self.write({"state": "published"})
