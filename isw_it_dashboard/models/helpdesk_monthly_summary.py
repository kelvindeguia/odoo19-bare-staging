from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .helpdesk_monthly_target import MONTH_SELECTION


class ITHelpdeskMonthlySummary(models.Model):
    _name = "it.helpdesk.monthly.summary"
    _description = "Jr. IT and Helpdesk Monthly Summary"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "year desc, month desc, id desc"
    _rec_name = "name"
    _check_company_auto = True

    name = fields.Char(
        string="Summary",
        compute="_compute_name",
        store=True,
        index=True,
    )
    month = fields.Selection(
        selection=MONTH_SELECTION,
        string="Month",
        required=True,
        default=lambda self: str(date.today().month),
        tracking=True,
        index=True,
    )
    year = fields.Integer(
        string="Year",
        required=True,
        default=lambda self: date.today().year,
        tracking=True,
        index=True,
    )
    period_date = fields.Date(
        string="Period Date",
        compute="_compute_period_date",
        store=True,
        index=True,
        help="First day of the selected month. Intended for QuickSight date filtering.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
        index=True,
    )
    target_id = fields.Many2one(
        comodel_name="it.helpdesk.monthly.target",
        string="Monthly Target",
        required=True,
        tracking=True,
        check_company=True,
        domain="[('month', '=', month), ('year', '=', year), ('company_id', '=', company_id), ('active', '=', True)]",
    )

    projected_ongoing_projects = fields.Integer(
        string="Projected/Ongoing Projects",
        tracking=True,
    )
    new_hire_pc_prepared = fields.Integer(
        string="New Hire PCs Prepared",
        tracking=True,
    )
    total_new_hires = fields.Integer(
        string="Total New Hires",
        tracking=True,
    )
    fallout_count = fields.Integer(
        string="Fallout Count",
        tracking=True,
    )
    pc_preparation_rate = fields.Float(
        string="PC Preparation Rate (%)",
        compute="_compute_pc_preparation_rate",
        store=True,
        digits=(16, 2),
    )

    neo_satisfaction_score = fields.Float(
        string="NEO Satisfaction Score",
        tracking=True,
        digits=(16, 2),
    )
    neo_target = fields.Float(
        string="NEO Target",
        related="target_id.neo_target",
        store=True,
        readonly=True,
        digits=(16, 2),
    )
    helpdesk_csat = fields.Float(
        string="Helpdesk CSAT (%)",
        tracking=True,
        digits=(16, 2),
    )
    helpdesk_csat_target = fields.Float(
        string="Helpdesk CSAT Target (%)",
        related="target_id.helpdesk_csat_target",
        store=True,
        readonly=True,
        digits=(16, 2),
    )
    helpdesk_ticket_kpi = fields.Float(
        string="Helpdesk Ticket KPI (%)",
        tracking=True,
        digits=(16, 2),
    )
    helpdesk_ticket_kpi_target = fields.Float(
        string="Helpdesk Ticket KPI Target (%)",
        related="target_id.helpdesk_ticket_kpi_target",
        store=True,
        readonly=True,
        digits=(16, 2),
    )

    remarks = fields.Text(string="Remarks", tracking=True)
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("review", "For Review"),
            ("approved", "Approved"),
            ("locked", "Locked"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    prepared_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Prepared By",
        default=lambda self: self.env.user,
        tracking=True,
    )
    approved_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Approved By",
        readonly=True,
        tracking=True,
    )
    approved_at = fields.Datetime(
        string="Approved At",
        readonly=True,
        tracking=True,
    )

    _unique_month_year_company = models.Constraint(
        "UNIQUE(month, year, company_id)",
        "Only one Jr. IT and Helpdesk summary is allowed per month, year, and company.",
    )

    @api.depends("month", "year")
    def _compute_name(self):
        month_names = dict(MONTH_SELECTION)
        for record in self:
            if record.month and record.year:
                record.name = _("Jr. IT and Helpdesk Summary - %(month)s %(year)s") % {
                    "month": month_names.get(record.month),
                    "year": record.year,
                }
            else:
                record.name = _("New Monthly Summary")

    @api.depends("month", "year")
    def _compute_period_date(self):
        for record in self:
            if record.month and record.year:
                try:
                    record.period_date = date(record.year, int(record.month), 1)
                except (TypeError, ValueError):
                    record.period_date = False
            else:
                record.period_date = False

    @api.depends("new_hire_pc_prepared", "total_new_hires")
    def _compute_pc_preparation_rate(self):
        for record in self:
            record.pc_preparation_rate = (
                (record.new_hire_pc_prepared / record.total_new_hires) * 100
                if record.total_new_hires
                else 0.0
            )

    @api.model_create_multi
    def create(self, vals_list):
        target_model = self.env["it.helpdesk.monthly.target"]
        for vals in vals_list:
            if not vals.get("target_id"):
                month = vals.get("month") or str(date.today().month)
                year = vals.get("year") or date.today().year
                company_id = vals.get("company_id") or self.env.company.id
                target = target_model.search(
                    [
                        ("month", "=", month),
                        ("year", "=", year),
                        ("company_id", "=", company_id),
                        ("active", "=", True),
                    ],
                    limit=1,
                )
                if target:
                    vals["target_id"] = target.id
        return super().create(vals_list)

    @api.onchange("month", "year", "company_id")
    def _onchange_reporting_period(self):
        for record in self:
            record.target_id = False
            if record.month and record.year and record.company_id:
                record.target_id = self.env["it.helpdesk.monthly.target"].search(
                    [
                        ("month", "=", record.month),
                        ("year", "=", record.year),
                        ("company_id", "=", record.company_id.id),
                        ("active", "=", True),
                    ],
                    limit=1,
                )

    @api.constrains("target_id", "month", "year", "company_id")
    def _check_target_reporting_period(self):
        for record in self:
            if not record.target_id:
                continue
            if record.target_id.month != record.month or record.target_id.year != record.year:
                raise ValidationError(_("The selected target must match the summary month and year."))
            if record.target_id.company_id != record.company_id:
                raise ValidationError(_("The selected target belongs to another company."))
            if not record.target_id.active:
                raise ValidationError(_("The selected monthly target is archived."))

    @api.constrains(
        "year",
        "projected_ongoing_projects",
        "new_hire_pc_prepared",
        "total_new_hires",
        "fallout_count",
        "neo_satisfaction_score",
        "helpdesk_csat",
        "helpdesk_ticket_kpi",
    )
    def _check_values(self):
        for record in self:
            if record.year < 2000 or record.year > 2100:
                raise ValidationError(_("The year must be between 2000 and 2100."))
            if any(
                value < 0
                for value in (
                    record.projected_ongoing_projects,
                    record.new_hire_pc_prepared,
                    record.total_new_hires,
                    record.fallout_count,
                )
            ):
                raise ValidationError(_("Counts cannot be negative."))
            if record.new_hire_pc_prepared > record.total_new_hires:
                raise ValidationError(_("Prepared PCs cannot exceed Total New Hires."))
            if record.new_hire_pc_prepared + record.fallout_count > record.total_new_hires:
                raise ValidationError(_("Prepared PCs plus Fallout cannot exceed Total New Hires."))
            if not 0 <= record.neo_satisfaction_score <= 5:
                raise ValidationError(_("The NEO Satisfaction Score must be between 0 and 5."))
            if not 0 <= record.helpdesk_csat <= 100:
                raise ValidationError(_("Helpdesk CSAT must be between 0 and 100."))
            if not 0 <= record.helpdesk_ticket_kpi <= 100:
                raise ValidationError(_("Helpdesk Ticket KPI must be between 0 and 100."))

    def write(self, vals):
        locked_records = self.filtered(lambda record: record.state == "locked")
        allowed_locked_fields = {"message_follower_ids", "message_partner_ids"}
        if locked_records and set(vals) - allowed_locked_fields:
            if not self.env.user.has_group("isw_it_dashboard.group_it_dashboard_admin"):
                raise AccessError(_("Locked monthly summaries can only be changed by an IT Dashboard Administrator."))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda record: record.state == "locked"):
            if not self.env.user.has_group("isw_it_dashboard.group_it_dashboard_admin"):
                raise AccessError(_("Locked monthly summaries can only be deleted by an IT Dashboard Administrator."))
        return super().unlink()

    def action_submit_for_review(self):
        if not self.env.user.has_group("isw_it_dashboard.group_it_dashboard_encoder"):
            raise AccessError(_("Only a Data Encoder or a higher role can submit a summary."))
        for record in self:
            if record.state != "draft":
                raise UserError(_("Only draft summaries can be submitted for review."))
            record.state = "review"
        return True

    def action_approve(self):
        if not self.env.user.has_group("isw_it_dashboard.group_it_dashboard_approver"):
            raise AccessError(_("Only an IT Dashboard Approver can approve a summary."))
        for record in self:
            if record.state != "review":
                raise UserError(_("Only summaries under review can be approved."))
            record.write({
                "state": "approved",
                "approved_by_id": self.env.user.id,
                "approved_at": fields.Datetime.now(),
            })
        return True

    def action_lock(self):
        if not self.env.user.has_group("isw_it_dashboard.group_it_dashboard_approver"):
            raise AccessError(_("Only an IT Dashboard Approver can lock a summary."))
        for record in self:
            if record.state != "approved":
                raise UserError(_("Only approved summaries can be locked."))
            record.state = "locked"
        return True

    def action_reset_to_draft(self):
        if not self.env.user.has_group("isw_it_dashboard.group_it_dashboard_admin"):
            raise AccessError(_("Only an IT Dashboard Administrator can reset a summary."))
        self.write({
            "state": "draft",
            "approved_by_id": False,
            "approved_at": False,
        })
        return True
