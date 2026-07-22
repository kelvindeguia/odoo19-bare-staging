from odoo import api, fields, models


class ITPCPreparation(models.Model):
    _name = "it.pc.preparation"
    _description = "New Hire PC Preparation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "required_date desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    period_id = fields.Many2one("it.dashboard.period", required=True, ondelete="cascade", index=True)
    employee_id = fields.Many2one("hr.employee", index=True)
    employee_name = fields.Char(required=True, tracking=True)
    obt_number = fields.Char(index=True)
    company_category = fields.Selection([("isupport", "iSupport"), ("iswerk", "iSWerk"), ("other", "Other")], required=True, index=True)
    department_id = fields.Many2one("hr.department")
    job_title = fields.Char()
    start_date = fields.Date(index=True)
    required_date = fields.Date(required=True, index=True)
    prepared_date = fields.Date(index=True)
    released_date = fields.Date(index=True)
    cancelled_date = fields.Date(index=True)
    status = fields.Selection([
        ("projected", "Projected"),
        ("pending", "Pending"),
        ("preparing", "In Preparation"),
        ("prepared", "Prepared"),
        ("released", "Released"),
        ("fallout", "Fallout"),
        ("cancelled", "Cancelled"),
    ], default="projected", required=True, tracking=True, index=True)
    fallout_reason = fields.Text()
    assigned_it_user_id = fields.Many2one("res.users", tracking=True)
    device_reference = fields.Char()
    source_type = fields.Selection([("manual", "Manual"), ("hrms", "Odoo HRMS"), ("import", "Imported")], default="manual")
    prepared_on_time = fields.Boolean(compute="_compute_prepared_on_time", store=True)

    @api.depends("employee_name", "required_date")
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.employee_name or 'New Hire'} - {rec.required_date or ''}"

    @api.depends("prepared_date", "required_date")
    def _compute_prepared_on_time(self):
        for rec in self:
            rec.prepared_on_time = bool(rec.prepared_date and rec.required_date and rec.prepared_date <= rec.required_date)

    @api.constrains("status", "fallout_reason")
    def _check_fallout_reason(self):
        for rec in self:
            if rec.status == "fallout" and not rec.fallout_reason:
                from odoo.exceptions import ValidationError
                raise ValidationError("A fallout reason is required when the status is Fallout.")
