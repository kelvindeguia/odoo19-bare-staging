from datetime import timedelta

from odoo import api, fields, models


class ITDashboardSummary(models.Model):
    _name = "it.dashboard.summary"
    _description = "IT Dashboard Summary"
    _inherit = ['it.dashboard.weekly.mixin']

    filter_type = fields.Selection(
        [("week", "Week"), ("year", "Year")],
        default="week",
        required=True,
    )
    start_date = fields.Date(default=lambda self: self._current_start_date())
    data = fields.Json(compute="_compute_data", store=False)

    helpdesk_ongoing_projects = fields.Integer(compute="_compute_data", store=True)
    new_hires_prepared = fields.Char(compute="_compute_data", store=True)
    fallout = fields.Integer(compute="_compute_data", store=True)
    neo_score = fields.Float(compute="_compute_data", store=True)
    neo_target = fields.Float(compute="_compute_data", store=True)
    csat = fields.Float(compute="_compute_data", store=True)
    ticket_kpi = fields.Float(compute="_compute_data", store=True)

    total_new_hires_actual = fields.Integer(compute="_compute_data", store=True)
    isupport = fields.Integer(compute="_compute_data", store=True)
    iswerk = fields.Integer(compute="_compute_data", store=True)

    total_new_hires_projected = fields.Integer(compute="_compute_data", store=True)
    projected_isupport = fields.Integer(compute="_compute_data", store=True)
    projected_iswerk = fields.Integer(compute="_compute_data", store=True)

    infra_ongoing_projects = fields.Integer(compute="_compute_data", store=True)
    devops_ongoing_projects = fields.Integer(compute="_compute_data", store=True)
    active_compliances = fields.Integer(compute="_compute_data", store=True)
    compliance_report_entries = fields.Text(compute="_compute_data", store=True)
    overall_it_health_rating = fields.Char(compute="_compute_data", store=True)

    
    @api.model
    def _current_start_date(self):
        today = fields.Date.today()
        return today - timedelta(days=today.weekday())

    @api.model
    def _ensure_date(self, value):
        return fields.Date.from_string(value) if isinstance(value, str) else value

    @api.depends("filter_type", "start_date")
    def _compute_data(self):
        for rec in self:
            start_date = rec.start_date or rec._current_start_date()
            end_date = start_date + timedelta(days=6)
            payload = rec.get_dashboard_data(start_date, end_date)
            rec.data = payload

            vals = rec._summary_vals_from_payload(payload, start_date, end_date)
            vals.pop("summary_start", None)
            vals.pop("summary_end", None)

            for field_name, value in vals.items():
                rec[field_name] = value
    # for list and form view
    @api.model
    def _summary_vals_from_payload(self, payload, start_date, end_date):
        # maps the payload returned by get_dashboard_data().
#    

        summary = payload.get("summary", {})

        return {
            "summary_start": start_date,
            "summary_end": end_date,

            "helpdesk_ongoing_projects": summary.get("helpdesk_ongoing_projects", 0),
            "new_hires_prepared": summary.get("new_hires_prepared", ""),
            "fallout": summary.get("fallout", 0),
            "neo_score": summary.get("neo_score", 0),
            "neo_target": summary.get("neo_target", 0),
            "csat": summary.get("csat", 0),
            "ticket_kpi": summary.get("ticket_kpi", 0),
            "total_new_hires_actual": summary.get("total_new_hires_actual",0,),
            "isupport": summary.get("isupport",0,),
            "iswerk": summary.get("iswerk",0,),
            "total_new_hires_projected": summary.get("total_new_hires_projected",0,),
            "projected_isupport": summary.get("projected_isupport",0,),
            "projected_iswerk": summary.get("projected_iswerk",0,),
            "infra_ongoing_projects": summary.get("infra_ongoing_projects", 0),
            "devops_ongoing_projects": summary.get("devops_ongoing_projects", 0),
            "active_compliances": summary.get("active_compliances", 0),
            "compliance_report_entries": summary.get("compliance_report_entries_text", ""),
            "overall_it_health_rating": summary.get(
                "overall_it_health_rating",
                "",
            ),
        }


    @api.model
    def _is_week_complete(self, start_date, end_date):
    #   returns True when every department dashboard already exists for the reporting week.
        ctx = self._get_context_records(start_date, end_date)

        return all([
            bool(ctx["helpdesk"]),
            bool(ctx["infra"]),
            bool(ctx["devops"]),
            bool(ctx["compliance"]),
            bool(ctx["management"]),
        ])
    
    @api.model
    def _missing_departments(self, start_date, end_date):
        """Returns a list of department labels that have no record for this week."""
        ctx = self._get_context_records(start_date, end_date)
        labels = {
            "helpdesk": "Helpdesk & Junior IT",
            "infra": "Infrastructure",
            "devops": "DevOps",
            "compliance": "Compliance",
            "management": "Management",
        }
        return [label for key, label in labels.items() if not ctx.get(key)]

    @api.model
    def _is_week_complete(self, start_date, end_date):
        return not self._missing_departments(start_date, end_date)


    @api.model
    def generate_weekly_summary(self, start_date=None, end_date=None):

        start_date = self._ensure_date(start_date) or self._current_start_date()
        end_date = self._ensure_date(end_date) or (start_date + timedelta(days=6))

        payload = self.get_dashboard_data(start_date, end_date)

        summary = payload["summary"]

        vals = {

            "summary_start": start_date,
            "summary_end": end_date,

            "helpdesk_ongoing_projects":
                summary.get("helpdesk_ongoing_projects", 0),

            "new_hires_prepared":
                summary.get("new_hires_prepared", ""),

            "fallout":
                summary.get("fallout", 0),

            "neo_score":
                summary.get("neo_score", 0),

            "neo_target":
                summary.get("neo_target", 0),

            "csat":
                summary.get("csat", 0),

            "ticket_kpi":
                summary.get("ticket_kpi", 0),

            "total_new_hires_actual":
                summary.get("total_new_hires_actual", 0),

            "isupport":
                summary.get("isupport", 0),

            "iswerk":
                summary.get("iswerk", 0),

            "total_new_hires_projected":
                summary.get("total_new_hires_projected", 0),

            "projected_isupport":
                summary.get("projected_isupport", 0),

            "projected_iswerk":
                summary.get("projected_iswerk", 0),

            "infra_ongoing_projects":
                summary.get("infra_ongoing_projects", 0),

            "devops_ongoing_projects":
                summary.get("devops_ongoing_projects", 0),

            "active_compliances":
                summary.get("active_compliances", 0),

            "compliance_report_entries":
                summary.get("compliance_report_entries_text", ""),

            "overall_it_health_rating":
                summary.get("overall_it_health_rating", ""),

        }

        record = self.search([
            ("summary_start", "=", start_date),
            ("summary_end", "=", end_date),
        ], limit=1)

        if record:
            record.write(vals)
            return record

        return self.create(vals)

    @api.model
    def sync_current_week(self):
    #    synchronize the current reporting week.

        start_date = self._current_start_date()
        end_date = start_date + timedelta(days=6)

        return self.generate_weekly_summary(
            start_date,
            end_date,
        )


    @api.model
    def sync_week(self, start_date, end_date):

        return self.generate_weekly_summary(
            start_date,
            end_date,
        )

    # every template from exactly one search call, fetched once here.
    @api.model
    def _get_overlapping_records(self, model, start_date, end_date, limit=None):
        return self.env[model].search(
            [
                ("summary_start", "<=", end_date),
                ("summary_end", ">=", start_date),
            ],
            order="summary_start desc, id desc",
            limit=limit,
        )

    @api.model
    def _get_single_record(self, model, start_date, end_date):
        return self._get_overlapping_records(model, start_date, end_date, limit=1)

    @api.model
    def _get_helpdesk_records(self, start_date, end_date):
        return self._get_overlapping_records("it.helpdesk.dashboard", start_date, end_date)

    @api.model
    def _get_compliance_records(self, start_date, end_date):
        return self._get_overlapping_records("it.compliance.dashboard", start_date, end_date)

    @api.model
    def _get_context_records(self, start_date, end_date):
        return {
            "helpdesk": self._get_helpdesk_records(start_date, end_date),
            "infra": self._get_single_record("it.infra.dashboard", start_date, end_date),
            "devops": self._get_single_record("it.devops.dashboard", start_date, end_date),
            "compliance": self._get_compliance_records(start_date, end_date),
            "management": self._get_single_record("it.management.dashboard", start_date, end_date),
        }

    @api.model
    def _get_compliance_entries(self, records):

        entries = []
        seen = set()

        stage_map = dict(
            self.env["it.active.compliance"]
            ._fields["stage"]
            .selection
        )

        for dashboard in records:
            for compliance in dashboard.compliances:

                key = compliance.id
                if key in seen:
                    continue

                seen.add(key)

                entries.append({
                    "id": compliance.id,
                    "name": compliance.name,
                    "stage": stage_map.get(
                        compliance.stage,
                        compliance.stage or "-"
                    ),
                })

        return entries
    @api.model
    def get_dashboard_data(self, start_date=None, end_date=None):
        start_date = self._ensure_date(start_date) or self._current_start_date()
        end_date = self._ensure_date(end_date) or (start_date + timedelta(days=6))

        ctx = self._get_context_records(start_date, end_date)
        return self._build_payload(ctx, start_date, end_date)

    @api.model
    def _get_latest_helpdesk_reports(self, records):
        rec = records[:1] and records[0] or False

        if not rec:
            return {
                "ticket_count": 0,
                "tickets_from_web": 0,
                "tickets_from_email": 0,
                "tickets_from_phone": 0,
                "first_response_time": "",
                "response_time": "",
                "resolution_time": "",
                "good_rating": 0,
                "okay_rating": 0,
                "bad_rating": 0,
                "new_tickets": 0,
                "on_hold_tickets": 0,
                "closed_tickets": 0,
                "backlog_tickets": 0,
            }

        return {
            "ticket_count": rec.ticket_count or 0,
            "tickets_from_web": rec.tickets_from_web or 0,
            "tickets_from_email": rec.tickets_from_email or 0,
            "tickets_from_phone": rec.tickets_from_phone or 0,
            "first_response_time": (
                rec.first_response_time or ""
            ),
            "response_time": rec.response_time or "",
            "resolution_time": rec.resolution_time or "",
            "good_rating": rec.good_rating or 0,
            "okay_rating": rec.okay_rating or 0,
            "bad_rating": rec.bad_rating or 0,
            "new_tickets": rec.new_tickets or 0,
            "on_hold_tickets": rec.on_hold_tickets or 0,
            "closed_tickets": rec.closed_tickets or 0,
            "backlog_tickets": rec.backlog_tickets or 0,
        }

    def _get_helpdesk_ticket_remarks(self,records):
        return [
            {
                "id": r.id,
                "new_count": r.new_count,
                "on_hold": r.on_hold,
                "closed": r.closed,
            }
            for r in records
        ]

    @api.model
    def _get_helpdesk_kpi_table(self, records):
        return [
            {
                "id": r.id,
                "name": r.name,
                "summary_date": (
                    f"{r.summary_start.strftime('%B %d, %Y')} – "
                    f"{r.summary_end.strftime('%B %d, %Y')}"
                    if r.summary_start and r.summary_end else ""
                ),
                "frt_prob": r.frt_prob or "",
                "frt_req": r.frt_req or "",
                "ert_prob": r.ert_prob or "",
                "ert_req": r.ert_req or "",
                "rt_prob": r.rt_prob or "",
                "rt_req": r.rt_req or "",
                "sla_achieved": r.sla_achieved or "",
                "happiness_ratings": r.happiness_ratings or "",
            }
            for r in records
        ]

    @api.model
    def _get_helpdesk_ticket_table(self, records):

        rec = records[:1]

        if not rec:
            return []

        rec = rec[0]

        return [{
            "id": rec.id,
            "incident_in_progress": rec.ticket_incident_in_progress or 0,
            "incident_on_hold": rec.ticket_incident_on_hold or 0,
            "incident_resolved": rec.ticket_incident_resolved or 0,
            "request_in_progress": rec.ticket_request_in_progress or 0,
            "request_on_hold": rec.ticket_request_on_hold or 0,
            "request_resolved": rec.ticket_request_resolved or 0,
        }]

    @api.model
    def _get_helpdesk_pc_prep_charts(self, records):
        if not records:
            return {"actual": {"labels": [], "datasets": []}, "projected": {"labels": [], "datasets": []}}

        onsite = sum(r.pc_preparation_onsite or 0 for r in records)
        wfh = sum(r.pc_preparation_wfh or 0 for r in records)
        proj_onsite = sum(r.projected_pc_preparation_onsite or 0 for r in records)
        proj_wfh = sum(r.projected_pc_preparation_wfh or 0 for r in records)

        return {
            "actual": {
                "labels": ["Onsite", "WFH"],
                "datasets": [{
                    "label": "Completed",
                    "data": [onsite, wfh],
                    "backgroundColor": ["#3b82f6", "#3b82f6"],
                }],
            },
            "projected": {
                "labels": ["Onsite", "WFH"],
                "datasets": [{
                    "label": "Projected",
                    "data": [proj_onsite, proj_wfh],
                    "backgroundColor": ["#f97316", "#f97316"],
                }],
            },
        }

    @api.model
    def _build_payload(self, ctx, start_date, end_date):
        helpdesk_records = ctx.get("helpdesk", self.env["it.helpdesk.dashboard"])
        helpdesk = helpdesk_records[:1] and helpdesk_records[0] or False
        infra = ctx.get("infra")
        devops = ctx.get("devops")
        compliance_records = ctx.get("compliance", self.env["it.compliance.dashboard"])
        compliance = compliance_records[:1] and compliance_records[0] or False
        management = ctx.get("management")
        compliance_entries = self._get_compliance_entries(compliance_records)
        compliance_entries_text = "\n".join(
            f"{entry['name']} - {entry['stage']}" for entry in compliance_entries
        )

        summary = {
            "summary_date": (
                f"{helpdesk.summary_start.strftime('%B %d, %Y')} – "
                f"{helpdesk.summary_end.strftime('%B %d, %Y')}"
                if helpdesk and helpdesk.summary_start and helpdesk.summary_end else ""
            ),

            # ---- Helpdesk overview card ----
            "helpdesk_ongoing_projects": helpdesk.helpdesk_ongoing_projects if helpdesk else 0,
            "new_hires_prepared": helpdesk.new_hires_prepared if helpdesk else "",
            "fallout": helpdesk.fallout if helpdesk else 0,
            "neo_score": helpdesk.neo_score if helpdesk else 0,
            "neo_target": helpdesk.neo_target if helpdesk else 0,
            "csat": helpdesk.csat if helpdesk else 0,
            "csat_target": helpdesk.csat_target if helpdesk else 0,
            "ticket_kpi": helpdesk.ticket_kpi if helpdesk else 0,
            "ticket_kpi_target": helpdesk.ticket_kpi_target if helpdesk else 0,

            # ---- Zoho Desk weekly metrics ----
            "ticket_count": helpdesk.ticket_count if helpdesk else 0,
            "tickets_from_web": helpdesk.tickets_from_web if helpdesk else 0,
            "tickets_from_email": helpdesk.tickets_from_email if helpdesk else 0,
            "tickets_from_phone": helpdesk.tickets_from_phone if helpdesk else 0,

            "first_response_time": (
                helpdesk.first_response_time
                if helpdesk else ""
            ),
            "response_time": (
                helpdesk.response_time
                if helpdesk else ""
            ),
            "resolution_time": (
                helpdesk.resolution_time
                if helpdesk else ""
            ),

            "good_rating": helpdesk.good_rating if helpdesk else 0,
            "okay_rating": helpdesk.okay_rating if helpdesk else 0,
            "bad_rating": helpdesk.bad_rating if helpdesk else 0,

            "new_tickets": helpdesk.new_tickets if helpdesk else 0,
            "on_hold_tickets": helpdesk.on_hold_tickets if helpdesk else 0,
            "closed_tickets": helpdesk.closed_tickets if helpdesk else 0,
            "backlog_tickets": helpdesk.backlog_tickets if helpdesk else 0,
    
            "total_new_hires_actual": helpdesk.total_new_hires_actual if helpdesk else 0,
            "isupport": helpdesk.isupport if helpdesk else 0,
            "iswerk": helpdesk.iswerk if helpdesk else 0,
            "total_new_hires_projected": helpdesk.total_new_hires_projected if helpdesk else 0,
            "projected_isupport": helpdesk.projected_isupport if helpdesk else 0,
            "projected_iswerk": helpdesk.projected_iswerk if helpdesk else 0,

            "neo_date_1": helpdesk.neo_date_1 if helpdesk else False,
            "neo_date_2": helpdesk.neo_date_2 if helpdesk else False,
            "neo_date_3": helpdesk.neo_date_3 if helpdesk else False,
            "neo_date_4": helpdesk.neo_date_4 if helpdesk else False,

            "neo_score_1": helpdesk.neo_score_1 if helpdesk else 0,
            "neo_score_2": helpdesk.neo_score_2 if helpdesk else 0,
            "neo_score_3": helpdesk.neo_score_3 if helpdesk else 0,
            "neo_score_4": helpdesk.neo_score_4 if helpdesk else 0,

            "overall_neo_score": helpdesk.overall_neo_score if helpdesk else 0,

            "comments_1": helpdesk.comments_1 if helpdesk else "",
            "comments_2": helpdesk.comments_2 if helpdesk else "",
            "comments_3": helpdesk.comments_3 if helpdesk else "",
            "comments_4": helpdesk.comments_4 if helpdesk else "",

            # ---- Infra overview card ----
            "infra_ongoing_projects": infra.infra_ongoing_projects if infra else 0,
            "network_uptime": infra.network_uptime if infra else 0,
            "server_uptime": infra.server_uptime if infra else 0,
            "telephony_uptime": infra.telephony_uptime if infra else 0,
            "internet_uptime": infra.internet_uptime if infra else 0,
            "security_breach": infra.security_breach if infra else 0,

            # ---- DevOps overview card ----
            "devops_ongoing_projects": devops.devops_ongoing_projects if devops else 0,
            "sprint_tasks_completed": devops.sprint_tasks_completed if devops else 0,
            "issues_raised": devops.issues_raised if devops else 0,
            "system_uptime": devops.system_uptime if devops else 0,
            "cloud_servers_uptime": devops.cloud_servers_uptime if devops else 0,

            # ---- Compliance overview card ----
            "active_compliances": len(compliance_entries) if compliance_entries else (compliance.active_compliances if compliance else 0),
            "compliance_stage_summary": compliance.compliance_stage_summary if compliance else "",
            "compliance_report_entries": compliance_entries,
            "compliance_report_entries_text": compliance_entries_text,

            # ---- Management overview card ----
            "overall_it_health_rating": management.overall_it_health_rating if management else "",
            "happiness_satisfaction_rating": management.happiness_satisfaction_rating if management else "",

            "missing_departments": self._missing_departments(start_date, end_date),
        }

        return {
            "start_date": start_date,
            "end_date": end_date,

            "summary": summary,

            "helpdesk_kpi_table": self._get_helpdesk_kpi_table(helpdesk_records),
            "helpdesk_ticket_table": self._get_helpdesk_ticket_table(helpdesk_records),
            "helpdesk_ticket_remarks": self._get_helpdesk_ticket_remarks(helpdesk_records),
            "latest_helpdesk_reports": self._get_latest_helpdesk_reports(helpdesk_records),
            "helpdesk_pc_prep": self._get_helpdesk_pc_prep_charts(helpdesk_records),

            "active_compliances": summary["active_compliances"],
            "compliance_stage_summary": summary["compliance_stage_summary"],
            "overall_it_health_rating": summary["overall_it_health_rating"],
        }
