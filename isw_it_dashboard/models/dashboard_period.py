from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ITDashboardPeriod(models.Model):
    _name = "it.dashboard.period"
    _description = "IT Dashboard Reporting Period"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_from desc, id desc"

    name = fields.Char(required=True, tracking=True, default=lambda self: _("New"))
    period_type = fields.Selection([
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
    ], required=True, default="monthly", tracking=True, index=True)
    date_from = fields.Date(required=True, tracking=True, index=True)
    date_to = fields.Date(required=True, tracking=True, index=True)
    state = fields.Selection([
        ("draft", "Draft"),
        ("collection", "Data Collection"),
        ("review", "For Review"),
        ("approved", "Approved"),
        ("locked", "Locked"),
    ], default="draft", required=True, tracking=True, index=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    prepared_by_id = fields.Many2one("res.users", default=lambda self: self.env.user, tracking=True)
    reviewed_by_id = fields.Many2one("res.users", tracking=True)
    approved_by_id = fields.Many2one("res.users", tracking=True)
    approved_date = fields.Datetime(readonly=True, tracking=True)
    locked_date = fields.Datetime(readonly=True, tracking=True)
    previous_period_id = fields.Many2one("it.dashboard.period", compute="_compute_previous_period", store=True)
    executive_summary = fields.Html(tracking=True)
    management_comment = fields.Html(tracking=True)
    kpi_result_ids = fields.One2many("it.dashboard.kpi.result", "period_id")
    neo_session_ids = fields.One2many("it.neo.session", "period_id")
    pc_preparation_ids = fields.One2many("it.pc.preparation", "period_id")
    highlight_ids = fields.One2many("it.department.highlight", "period_id")
    project_update_ids = fields.One2many("it.project.update", "period_id")
    kpi_count = fields.Integer(compute="_compute_counts")
    neo_count = fields.Integer(compute="_compute_counts")
    pc_count = fields.Integer(compute="_compute_counts")
    highlight_count = fields.Integer(compute="_compute_counts")
    project_count = fields.Integer(compute="_compute_counts")
    completion_percentage = fields.Float(compute="_compute_completion", store=False)

    _valid_dates = models.Constraint(
        "CHECK(date_to >= date_from)",
        "The end date must be on or after the start date.",
    )
    _unique_period = models.Constraint(
        "UNIQUE(period_type, date_from, date_to, company_id)",
        "A reporting period with the same type and dates already exists for this company.",
    )

    @api.depends("date_from", "period_type", "company_id")
    def _compute_previous_period(self):
        for rec in self:
            rec.previous_period_id = False
            if rec.date_from and rec.company_id:
                rec.previous_period_id = self.search([
                    ("company_id", "=", rec.company_id.id),
                    ("period_type", "=", rec.period_type),
                    ("date_to", "<", rec.date_from),
                ], order="date_to desc", limit=1)

    @api.depends("kpi_result_ids", "neo_session_ids", "pc_preparation_ids", "highlight_ids", "project_update_ids")
    def _compute_counts(self):
        for rec in self:
            rec.kpi_count = len(rec.kpi_result_ids)
            rec.neo_count = len(rec.neo_session_ids)
            rec.pc_count = len(rec.pc_preparation_ids)
            rec.highlight_count = len(rec.highlight_ids)
            rec.project_count = len(rec.project_update_ids)

    def _compute_completion(self):
        for rec in self:
            checks = [bool(rec.kpi_result_ids), bool(rec.highlight_ids)]
            if rec.period_type == "monthly":
                checks += [bool(rec.neo_session_ids), bool(rec.pc_preparation_ids)]
            rec.completion_percentage = 100.0 * sum(checks) / len(checks) if checks else 0.0

    @api.onchange("period_type", "date_from")
    def _onchange_period_dates(self):
        for rec in self:
            if not rec.date_from:
                continue
            if rec.period_type == "daily":
                rec.date_to = rec.date_from
            elif rec.period_type == "weekly":
                rec.date_to = rec.date_from + timedelta(days=6)
            elif rec.period_type == "monthly":
                next_month = fields.Date.add(rec.date_from.replace(day=1), months=1)
                rec.date_from = rec.date_from.replace(day=1)
                rec.date_to = next_month - timedelta(days=1)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name") in (False, _("New"), "New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("it.dashboard.period") or _("New")
        return super().create(vals_list)

    def write(self, vals):
        if any(rec.state == "locked" for rec in self) and not self.env.user.has_group("isw_it_dashboard.group_it_dashboard_admin"):
            raise UserError(_("Locked reporting periods can only be modified by an IT Dashboard Administrator."))
        return super().write(vals)

    def action_start_collection(self):
        self.write({"state": "collection"})

    def action_submit_review(self):
        for rec in self:
            if rec.completion_percentage < 100:
                raise ValidationError(_("Complete the required data sections before submitting for review."))
        self.write({"state": "review"})

    def action_approve(self):
        self.write({"state": "approved", "approved_by_id": self.env.user.id, "approved_date": fields.Datetime.now()})

    def action_lock(self):
        self.write({"state": "locked", "locked_date": fields.Datetime.now()})

    def action_reopen(self):
        if not self.env.user.has_group("isw_it_dashboard.group_it_dashboard_admin"):
            raise UserError(_("Only an IT Dashboard Administrator can reopen a period."))
        self.write({"state": "review", "locked_date": False})
