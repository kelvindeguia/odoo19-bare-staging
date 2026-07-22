from odoo import api, fields, models


class ITDashboardKPI(models.Model):
    _name = "it.dashboard.kpi"
    _description = "IT Dashboard KPI Definition"
    _order = "category, sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    category = fields.Selection([
        ("helpdesk", "Helpdesk"),
        ("neo", "NEO Satisfaction"),
        ("pc", "PC Preparation"),
        ("project", "Projects"),
        ("general", "General"),
    ], required=True, default="general", index=True)
    unit = fields.Selection([
        ("number", "Number"),
        ("percentage", "Percentage"),
        ("score", "Score"),
        ("minutes", "Minutes"),
        ("hours", "Hours"),
    ], default="number", required=True)
    target_value = fields.Float()
    higher_is_better = fields.Boolean(default=True)
    data_source = fields.Selection([
        ("manual", "Manual"),
        ("zoho", "Zoho Desk"),
        ("odoo", "Odoo"),
        ("calculated", "Calculated"),
        ("import", "Imported File"),
    ], default="manual", required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _unique_code = models.Constraint("UNIQUE(code)", "The KPI code must be unique.")


class ITDashboardKPIResult(models.Model):
    _name = "it.dashboard.kpi.result"
    _description = "IT Dashboard KPI Result"
    _inherit = ["mail.thread"]
    _order = "period_id desc, kpi_id"

    period_id = fields.Many2one("it.dashboard.period", required=True, ondelete="cascade", index=True)
    kpi_id = fields.Many2one("it.dashboard.kpi", required=True, index=True)
    actual_value = fields.Float(tracking=True)
    numerator = fields.Float(tracking=True)
    denominator = fields.Float(tracking=True)
    target_value = fields.Float(related="kpi_id.target_value", store=True)
    achievement_percentage = fields.Float(compute="_compute_achievement", store=True)
    previous_value = fields.Float(compute="_compute_previous", store=True)
    variance = fields.Float(compute="_compute_previous", store=True)
    status = fields.Selection([
        ("achieved", "Achieved"),
        ("missed", "Missed"),
        ("neutral", "No Target"),
    ], compute="_compute_achievement", store=True)
    source_type = fields.Selection(related="kpi_id.data_source", store=True)
    source_reference = fields.Char()
    remarks = fields.Text()

    _unique_period_kpi = models.Constraint(
        "UNIQUE(period_id, kpi_id)",
        "Each KPI can only have one result per reporting period.",
    )

    @api.depends("actual_value", "numerator", "denominator", "target_value", "kpi_id.higher_is_better")
    def _compute_achievement(self):
        for rec in self:
            actual = rec.actual_value
            if rec.denominator:
                actual = (rec.numerator / rec.denominator) * 100.0
                rec.actual_value = actual
            rec.achievement_percentage = (actual / rec.target_value * 100.0) if rec.target_value else 0.0
            if not rec.target_value:
                rec.status = "neutral"
            elif rec.kpi_id.higher_is_better:
                rec.status = "achieved" if actual >= rec.target_value else "missed"
            else:
                rec.status = "achieved" if actual <= rec.target_value else "missed"

    @api.depends("period_id.previous_period_id", "kpi_id", "actual_value")
    def _compute_previous(self):
        for rec in self:
            previous = self.search([
                ("period_id", "=", rec.period_id.previous_period_id.id),
                ("kpi_id", "=", rec.kpi_id.id),
            ], limit=1) if rec.period_id.previous_period_id else False
            rec.previous_value = previous.actual_value if previous else 0.0
            rec.variance = rec.actual_value - rec.previous_value
