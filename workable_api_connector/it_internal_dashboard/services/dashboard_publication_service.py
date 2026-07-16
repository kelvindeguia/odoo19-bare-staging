"""
Token-scoped public dashboard data service.

This is the only public-facing code path that reads dashboard models.  It
returns the same view-model shape consumed by the internal OWL components,
while the public OWL workspace supplies ``publicMode=true`` so those components
render read-only and never call ORM services from the browser.
"""
import logging
from datetime import date, datetime, timedelta

_logger = logging.getLogger(__name__)


class DashboardPublicationService:
    SECTION_FLAGS = {
        "summary": "include_executive_summary",
        "helpdesk": "include_helpdesk",
        "infra": "include_infra",
        "devops": "include_devops",
        "compliance": "include_compliance",
        "management": "include_management",
    }

    def __init__(self, env, publication, window_start=None, window_end=None):
        self._env = env
        self._pub = publication
        if window_start and window_end:
            self._week_start = window_start
            self._week_end = window_end
        else:
            self._week_start, self._week_end = publication._default_window()

    def get_navigation(self):
        nav = []
        if self._section_included("summary"):
            nav.append({"key": "summary", "label": "Executive Dashboard Summary"})
        if self._section_included("helpdesk"):
            nav.append({"key": "helpdesk", "label": "Helpdesk & Junior IT"})
        if self._section_included("infra"):
            nav.append({"key": "infra", "label": "Infrastructure"})
        if self._section_included("devops"):
            nav.append({"key": "devops", "label": "DevOps"})
        if self._section_included("compliance"):
            nav.append({"key": "compliance", "label": "Compliance"})
        if self._section_included("management"):
            nav.append({"key": "management", "label": "Management"})
        return nav

    # ----------------------------------------------------------------
    # FIXED: Removed start_date / end_date parameters.
    # The publication already knows its week — accepting date overrides
    # from the browser would let an anonymous caller read arbitrary weeks
    # from your database using a valid token for a different week.
    # ----------------------------------------------------------------

    def get_full_payload(self, section: str) -> dict:
        """
        Return the public data payload for one dashboard section.
        The date window is always taken from self._pub — never from
        the caller.
        """
        handlers = {
            "helpdesk": self._get_helpdesk_payload,
            "infra": self._get_infra_payload,
            "devops": self._get_devops_payload,
            "compliance": self._get_compliance_payload,
            "management": self._get_management_payload,
            "summary": self._get_summary_payload,
        }

        handler = handlers.get(section)
        if not handler:
            return {"error": "Unknown section"}

        section_flag_map = {
            "helpdesk": self._pub.include_helpdesk,
            "infra": self._pub.include_infra,
            "devops": self._pub.include_devops,
            "compliance": self._pub.include_compliance,
            "management": self._pub.include_management,
            "summary": self._pub.include_executive_summary,
        }

        if not section_flag_map.get(section, False):
            return {"error": "Section not included in this publication"}

        try:
            return handler()
        except Exception as exc:
            _logger.error(
                "Error building public payload for section %s: %s",
                section, exc,
            )
            return {"error": "Data temporarily unavailable"}

    def _section_included(self, section):
        if section == "summary":
            return bool(self._pub.include_executive_summary)

        department_flags = [
            self._pub.include_helpdesk,
            self._pub.include_infra,
            self._pub.include_devops,
            self._pub.include_compliance,
            self._pub.include_management,
        ]
        legacy_all_department_share = (
            self._pub.include_executive_summary
            and not any(department_flags)
        )
        return legacy_all_department_share or bool(getattr(self._pub, self.SECTION_FLAGS[section]))

    def _get_record(self, model):
        return self._env[model].sudo().search(
            [
                ("summary_start", "<=", self._week_end),
                ("summary_end", ">=", self._week_start),
            ],
            order="summary_start desc, id desc",
            limit=1,
        )

    def _get_helpdesk_payload(self):
        record = self._get_record("it.helpdesk.dashboard")
        payload = {
            "summary_start": self._date_value(self._week_start),
            "summary_end": self._date_value(self._week_end),
            "viewMode": "readonly",
            "helpdesk_ongoing_projects": 0,
            "new_hires_prepared": "",
            "fallout": 0,
            "neo_score": 0,
            "neo_target": 0,
            "csat": 0,
            "csat_target": 0,
            "ticket_kpi": 0,
            "ticket_kpi_target": 0,
            "frt_prob": "",
            "frt_req": "",
            "ert_prob": "",
            "ert_req": "",
            "rt_prob": "",
            "rt_req": "",
            "sla_achieved": "",
            "happiness_ratings": "",
            "new_count": 0,
            "on_hold": 0,
            "closed": 0,
            "lighthouse_report": "",
            "neo_satisfaction_score": "",
            "new_tickets": "",
            "on_hold_tickets": "",
            "closed_tickets": "",
            "backlog_tickets": "",
            "lighthouse_report_url": "",
            "neo_satisfaction_score_url": "",
            "neo_date_1": "",
            "neo_date_2": "",
            "neo_date_3": "",
            "neo_date_4": "",
            "neo_score_1": 0,
            "neo_score_2": 0,
            "neo_score_3": 0,
            "neo_score_4": 0,
            "overall_neo_score": 0,
            "comments_1": "",
            "comments_2": "",
            "comments_3": "",
            "comments_4": "",
            "pc_preparation_onsite": 0,
            "pc_preparation_wfh": 0,
            "projected_pc_preparation_onsite": 0,
            "projected_pc_preparation_wfh": 0,
            "ticket_incident_in_progress": 0,
            "ticket_incident_on_hold": 0,
            "ticket_incident_resolved": 0,
            "ticket_request_in_progress": 0,
            "ticket_request_on_hold": 0,
            "ticket_request_resolved": 0,
            "isupport": 0,
            "iswerk": 0,
            "total_new_hires_actual": 0,
            "projected_isupport": 0,
            "projected_iswerk": 0,
            "total_new_hires_projected": 0,
            "helpdesk_kpis_attainment": "",
            "helpdesk_key_wins": "",
            "helpdesk_challenges": "",
            "helpdesk_help_needed": "",
        }
        if not record:
            return payload

        for field in payload:
            if field in ("viewMode", "lighthouse_report_url", "neo_satisfaction_score_url"):
                continue
            if field in record._fields:
                value = self._public_value(record[field])
                if value not in (False, None):
                    payload[field] = value

        if record.lighthouse_report:
            payload["lighthouse_report_url"] = self._get_image_url("helpdesk", "lighthouse_report")
        if record.neo_satisfaction_score:
            payload["neo_satisfaction_score_url"] = self._get_image_url("helpdesk", "neo_satisfaction_score")
        return payload

    def _get_infra_payload(self):
        record = self._get_record("it.infra.dashboard")
        payload = {
            "summary_start": self._date_value(self._week_start),
            "summary_end": self._date_value(self._week_end),
            "infra_ongoing_projects": 0,
            "network_uptime": "",
            "server_uptime": "",
            "security_breach": "",
            "telephony_uptime": "",
            "internet_uptime": "",
            "infra_kpis_attainment": "",
            "infra_key_wins": "",
            "infra_challenges": "",
            "infra_help_needed": "",
        }
        return self._copy_record_fields(record, payload)

    def _get_devops_payload(self):
        record = self._get_record("it.devops.dashboard")
        payload = {
            "summary_start": self._date_value(self._week_start),
            "summary_end": self._date_value(self._week_end),
            "devops_ongoing_projects": 0,
            "sprint_tasks_completed": 0,
            "issues_raised": 0,
            "system_uptime": "",
            "cloud_servers_uptime": "",
            "devops_kpis_attainment": "",
            "devops_key_wins": "",
            "devops_challenges": "",
            "devops_help_needed": "",
        }
        return self._copy_record_fields(record, payload)

    def _get_compliance_payload(self):
        record = self._get_record("it.compliance.dashboard")
        payload = {
            "summary_start": self._date_value(self._week_start),
            "summary_end": self._date_value(self._week_end),
            "compliance_summary_start": self._date_value(self._week_start),
            "compliance_summary_end": self._date_value(self._week_end),
            "active_compliances": 0,
            "current_compliance_stage": "",
        }
        return self._copy_record_fields(record, payload)

    def _get_management_payload(self):
        record = self._get_record("it.management.dashboard")
        payload = {
            "summary_start": self._date_value(self._week_start),
            "summary_end": self._date_value(self._week_end),
            "overall_it_health_rating": "",
            "happiness_satisfaction_rating": "",
        }
        return self._copy_record_fields(record, payload)

    def _get_summary_payload(self):
        payload = (
            self._env["it.dashboard.summary"]
            .sudo()
            .get_dashboard_data(self._week_start, self._week_end)
        )
        payload["start_date"] = self._date_value(self._week_start)
        payload["end_date"] = self._date_value(self._week_end)

        reports = payload.get("latest_helpdesk_reports") or {}
        if reports.get("lighthouse_report_url"):
            reports["lighthouse_report_url"] = self._get_image_url("helpdesk", "lighthouse_report")
        if reports.get("neo_satisfaction_score_url"):
            reports["neo_satisfaction_score_url"] = self._get_image_url("helpdesk", "neo_satisfaction_score")
        payload["latest_helpdesk_reports"] = reports

        for key in ("helpdesk_kpi_table", "helpdesk_ticket_table"):
            rows = payload.get(key) or []
            for index, row in enumerate(rows):
                row["id"] = f"{key}_{index}"

        pc_prep = payload.get("helpdesk_pc_prep") or {}
        pc_prep.setdefault("actual", self._empty_chart("Completed", "#3b82f6"))
        pc_prep.setdefault("projected", self._empty_chart("Projected", "#f97316"))
        if not pc_prep["actual"].get("labels"):
            pc_prep["actual"] = self._empty_chart("Completed", "#3b82f6")
        if not pc_prep["projected"].get("labels"):
            pc_prep["projected"] = self._empty_chart("Projected", "#f97316")
        payload["helpdesk_pc_prep"] = pc_prep

        return payload

    def _copy_record_fields(self, record, payload):
        if not record:
            return payload
        for field in payload:
            if field in record._fields:
                value = self._public_value(record[field])
                if value not in (False, None):
                    payload[field] = value
        return payload

    def _get_image_url(self, section, field):
        return (
            f"/it-internal-dashboard-test2/{self._pub.share_token}/image"
            f"?section={section}&field={field}"
            f"&start_date={self._date_value(self._week_start)}"
            f"&end_date={self._date_value(self._week_end)}"
        )

    def _empty_chart(self, label, color):
        return {
            "labels": ["Onsite", "WFH"],
            "datasets": [{
                "label": label,
                "data": [0, 0],
                "backgroundColor": [color, color],
            }],
        }

    def _date_value(self, value):
        return value.isoformat() if value else ""

    def _public_value(self, value):
        return value.isoformat() if hasattr(value, "isoformat") else value

    def _parse_date(self, value):
        if not value:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value))
        except ValueError:
            return None
