from odoo import models, fields, api
from datetime import timedelta
from odoo.exceptions import UserError

class ITDashboardSummaryHistory(models.Model):
    _name = "it.dashboard.summary.history"
    _description = "Executive Dashboard History"
    _inherit = ["it.dashboard.weekly.mixin"]

    _order = "summary_start desc"

    name = fields.Char(compute="_compute_name", store=True)

    is_complete = fields.Boolean(
        string="All Departments Submitted",
        default=False,
    )
    missing_departments = fields.Char(
        string="Pending Departments",
        default="",
    )

    helpdesk_ongoing_projects = fields.Integer()
    new_hires_prepared = fields.Char()
    fallout = fields.Integer()
    neo_score = fields.Float()
    neo_target = fields.Float()
    csat = fields.Float()
    ticket_kpi = fields.Float()
    infra_ongoing_projects = fields.Integer()
    devops_ongoing_projects = fields.Integer()
    active_compliances = fields.Integer()
    compliance_report_entries = fields.Text()
    overall_it_health_rating = fields.Char()

    _unique_summary_week_constraint = models.Constraint(
        "UNIQUE(summary_start, summary_end)",
        "Only one Executive Summary may exist for a reporting week.",
    )

    @api.depends("summary_start", "summary_end")
    def _compute_name(self):
        for rec in self:
            if rec.summary_start and rec.summary_end:
                rec.name = f"Executive Summary {rec.summary_start} - {rec.summary_end}"
            else:
                rec.name = "Executive Summary"

    @api.model
    def sync_week(self, start_date, end_date):
        """
        Always upserts a snapshot for the week, using whatever department
        data currently exists. Missing departments contribute defaults
        (0 / "") via _build_payload, and are surfaced through
        `is_complete` / `missing_departments` rather than blocking the sync.
        """
        summary_model = self.env["it.dashboard.summary"]
        missing = summary_model._missing_departments(start_date, end_date)

        payload = summary_model.get_dashboard_data(start_date, end_date)
        summary = payload["summary"]

        vals = {
            "summary_start": start_date,
            "summary_end": end_date,
            "is_complete": not missing,
            "missing_departments": ", ".join(missing),
            "helpdesk_ongoing_projects": summary.get("helpdesk_ongoing_projects", 0),
            "new_hires_prepared": summary.get("new_hires_prepared", ""),
            "fallout": summary.get("fallout", 0),
            "neo_score": summary.get("neo_score", 0),
            "neo_target": summary.get("neo_target", 0),
            "csat": summary.get("csat", 0),
            "ticket_kpi": summary.get("ticket_kpi", 0),
            "infra_ongoing_projects": summary.get("infra_ongoing_projects", 0),
            "devops_ongoing_projects": summary.get("devops_ongoing_projects", 0),
            "active_compliances": summary.get("active_compliances", 0),
            "compliance_report_entries": summary.get("compliance_report_entries_text", ""),
            "overall_it_health_rating": summary.get("overall_it_health_rating", ""),
        }

        history = self.search(
            [("summary_start", "=", start_date), ("summary_end", "=", end_date)],
            limit=1,
        )

        if history:
            history.write(vals)
            return history

        return self.create(vals)

    @api.model
    def sync_current_week(self):
        monday = fields.Date.today()
        monday -= timedelta(days=monday.weekday())
        sunday = monday + timedelta(days=6)
        return self.sync_week(monday, sunday)

    def write(self, vals):
        if not self.env.user.has_group("base.group_system"):
            raise UserError("Only administrators can edit Executive Summary History.")
        return super().write(vals)

    def unlink(self):
        if not self.env.user.has_group("base.group_system"):
            raise UserError("Only administrators can delete Executive Summary History.")
        return super().unlink()