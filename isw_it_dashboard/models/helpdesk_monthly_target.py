from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


MONTH_SELECTION = [
    ("1", "January"),
    ("2", "February"),
    ("3", "March"),
    ("4", "April"),
    ("5", "May"),
    ("6", "June"),
    ("7", "July"),
    ("8", "August"),
    ("9", "September"),
    ("10", "October"),
    ("11", "November"),
    ("12", "December"),
]


class ITHelpdeskMonthlyTarget(models.Model):
    _name = "it.helpdesk.monthly.target"
    _description = "Jr. IT and Helpdesk Monthly Target"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "year desc, month desc, id desc"
    _rec_name = "name"
    _check_company_auto = True

    name = fields.Char(
        string="Target Name",
        compute="_compute_name",
        store=True,
        index=True,
    )
    month = fields.Selection(
        selection=MONTH_SELECTION,
        string="Applicable Month",
        required=True,
        default=lambda self: str(date.today().month),
        tracking=True,
        index=True,
    )
    year = fields.Integer(
        string="Applicable Year",
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

    neo_target = fields.Float(
        string="NEO Satisfaction Target",
        default=4.50,
        required=True,
        digits=(16, 2),
        tracking=True,
    )
    helpdesk_csat_target = fields.Float(
        string="Helpdesk CSAT Target (%)",
        default=90.00,
        required=True,
        digits=(16, 2),
        tracking=True,
    )
    helpdesk_ticket_kpi_target = fields.Float(
        string="Helpdesk Ticket KPI Target (%)",
        default=85.00,
        required=True,
        digits=(16, 2),
        tracking=True,
    )
    active = fields.Boolean(default=True, tracking=True)
    notes = fields.Text(string="Target Notes", tracking=True)

    _unique_target_period = models.Constraint(
        "UNIQUE(month, year, company_id)",
        "Only one target configuration is allowed for each month, year, and company.",
    )

    @api.depends("month", "year")
    def _compute_name(self):
        month_names = dict(MONTH_SELECTION)
        for record in self:
            if record.month and record.year:
                record.name = _("Jr. IT and Helpdesk Targets - %(month)s %(year)s") % {
                    "month": month_names.get(record.month),
                    "year": record.year,
                }
            else:
                record.name = _("New Monthly Target")

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

    @api.constrains(
        "year",
        "neo_target",
        "helpdesk_csat_target",
        "helpdesk_ticket_kpi_target",
    )
    def _check_target_values(self):
        for record in self:
            if record.year < 2000 or record.year > 2100:
                raise ValidationError(_("The applicable year must be between 2000 and 2100."))
            if not 0 <= record.neo_target <= 5:
                raise ValidationError(_("The NEO target must be between 0 and 5."))
            if not 0 <= record.helpdesk_csat_target <= 100:
                raise ValidationError(_("The Helpdesk CSAT target must be between 0 and 100."))
            if not 0 <= record.helpdesk_ticket_kpi_target <= 100:
                raise ValidationError(_("The Helpdesk Ticket KPI target must be between 0 and 100."))
