from datetime import timedelta
from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError

class WeeklyDashboardMixin(models.AbstractModel):
    _name = "it.dashboard.weekly.mixin"
    _description = "Weekly Dashboard Mixin"

    created_by = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        readonly=True,
    )

    created_on = fields.Datetime(
        default=fields.Datetime.now,
        readonly=True,
    )

    summary_start = fields.Date(
        readonly=True,
    )

    summary_end = fields.Date(
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:

            created = fields.Datetime.to_datetime(
                vals.get("created_on") or fields.Datetime.now()
            ).date()

            monday = created - timedelta(days=created.weekday())
            sunday = monday + timedelta(days=6)

            vals["summary_start"] = monday
            vals["summary_end"] = sunday

        return super().create(vals_list)

    @api.constrains("summary_start")
    def _check_unique_week(self):
        for rec in self:
            existing = self.search(
                [
                    ("summary_start", "=", rec.summary_start),
                    ("id", "!=", rec.id),
                ],
                limit=1,
            )

            if existing:
                raise ValidationError(
                    f"A dashboard already exists for the week beginning {rec.summary_start}."
                )

    def write(self, vals):
        if not self.env.user.has_group("base.group_system"):
            for rec in self:
                if rec.create_uid.id != self.env.user.id:
                    raise UserError(
                        "Only the original creator or an administrator can modify this record."
                    )
        return super().write(vals)