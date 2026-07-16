from odoo import api, models, fields
from datetime import date, timedelta
from odoo.exceptions import UserError
import time
import json
import logging
from ..services.zoho_dashboard import ZohoDashboardService

_logger = logging.getLogger(__name__)

class HelpdeskDashboard(models.Model):
    _name = 'it.helpdesk.dashboard'
    _description = 'IT Helpdesk & Jr IT Dashboard'
    _inherit = ['it.dashboard.weekly.mixin'] 

    name = fields.Char(
        default=lambda self: f"Helpdesk & Junior IT Dashboard Input - {date.today()}"
    )

    _rec_name = 'name'

    helpdesk_ongoing_projects = fields.Integer(string="Projected/Ongoing Projects")
    new_hires_prepared = fields.Char(string="New Hire PCs Prepared (e.g. 57/61)")
    fallout = fields.Integer(string="Fallout")

    neo_score = fields.Float(string="NEO Score")
    neo_target = fields.Float(string="NEO Target")

    csat = fields.Float(string="CSAT (%)")
    csat_target = fields.Float(string="CSAT Target")

    ticket_kpi = fields.Float(string="Ticket KPI (%)")
    ticket_kpi_target = fields.Float(string="Ticket KPI Target")

    #  KPI TABLE (FRT / ERT / RT)
    frt_prob = fields.Char()
    frt_req = fields.Char()

    ert_prob = fields.Char()
    ert_req = fields.Char()

    rt_prob = fields.Char()
    rt_req = fields.Char()

    #  KPI SUMMARY
    sla_achieved = fields.Char()
    happiness_ratings = fields.Char()

    #  REMARKS
    new_count = fields.Integer()
    on_hold = fields.Integer()
    closed = fields.Integer()

    # ZOHO ANALYTICS
    ticket_count = fields.Integer()
    tickets_from_web = fields.Integer()
    tickets_from_email = fields.Integer()
    tickets_from_phone = fields.Integer()
    first_response_time = fields.Char()
    response_time = fields.Char()
    resolution_time = fields.Char()
    good_rating = fields.Integer()
    okay_rating = fields.Integer()
    bad_rating = fields.Integer()
    
    lighthouse_report = fields.Binary()
    neo_satisfaction_score = fields.Binary()
    
    new_tickets = fields.Integer()
    on_hold_tickets = fields.Integer()
    closed_tickets = fields.Integer()
    backlog_tickets = fields.Integer()

    neo_date_1= fields.Date()
    neo_score_1= fields.Float()
    neo_date_2= fields.Date()
    neo_score_2= fields.Float()
    neo_date_3= fields.Date()
    neo_score_3= fields.Float()
    neo_date_4= fields.Date()
    neo_score_4= fields.Float()

    overall_neo_score = fields.Float(string="Month MTD Overall NEO Score", compute="_compute_overall_neo_score")
    
    comments_1 = fields.Text()
    comments_2 = fields.Text()
    comments_3 = fields.Text()
    comments_4 = fields.Text()

    pc_preparation_onsite = fields.Integer(string="Onsite PCs Prepared")
    pc_preparation_wfh = fields.Integer(string="WFH PCs Prepared")

    projected_pc_preparation_onsite = fields.Integer(string="Projected Onsite PCs")
    projected_pc_preparation_wfh = fields.Integer(string="Projected WFH PCs")

    #  Chart fields
    pc_prep_chart = fields.Json(compute="_compute_charts", store=True)
    projected_pc_prep_chart = fields.Json(compute="_compute_charts", store=True)

    # THIS WEEK
    isupport = fields.Integer(string="iSupport (This Week)")
    iswerk = fields.Integer(string="iSWerk (This Week)")

    total_new_hires_actual = fields.Integer(
        compute="_compute_total_new_hires",
        store=True
    )

    # NEXT WEEK (PROJECTED)
    projected_isupport = fields.Integer(string="Projected iSupport")
    projected_iswerk = fields.Integer(string="Projected iSWerk")

    total_new_hires_projected = fields.Integer(
        compute="_compute_total_new_hires",
        store=True
    )

    ticket_incident_in_progress= fields.Integer(string="Ticket Incident In Progress")
    ticket_incident_on_hold= fields.Integer(string="Ticket Incident On Hold")
    ticket_incident_resolved= fields.Integer(string="Ticket Incident Resolved")

    ticket_request_in_progress= fields.Integer(string="Ticket Request In Progress")
    ticket_request_on_hold= fields.Integer(string="Ticket Request On Hold")
    ticket_request_resolved= fields.Integer(string="Ticket Request Resolved")

    #  TABLE (highlights)
    helpdesk_kpis_attainment = fields.Text()
    helpdesk_key_wins = fields.Text()
    helpdesk_challenges = fields.Text()
    helpdesk_help_needed = fields.Text()

    @api.depends(
        "isupport",
        "iswerk",
        "projected_isupport",
        "projected_iswerk",
    )
    def _compute_total_new_hires(self):
        for rec in self:
            #  THIS WEEK
            rec.total_new_hires_actual = (
                (rec.isupport or 0) +
                (rec.iswerk or 0)
            )

            #  PROJECTED
            rec.total_new_hires_projected = (
                (rec.projected_isupport or 0) +
                (rec.projected_iswerk or 0)
        )

    def _compute_charts(self):
        for rec in self:

            #  Chart 1: This week (Completed)
            rec.pc_prep_chart = {
                "labels": ["Onsite", "WFH"],
                "datasets": [
                    {
                        "label": "Completed",
                        "data": [
                            rec.pc_preparation_onsite or 0,
                            rec.pc_preparation_wfh or 0,
                        ],
                        "backgroundColor": "#1f6d8c"
                    }
                ]
            }

            #  Chart 2: Next week (Projected)
            rec.projected_pc_prep_chart = {
                "labels": ["Onsite", "WFH"],
                "datasets": [
                    {
                        "label": "Projected",
                        "data": [
                            rec.projected_pc_preparation_onsite or 0,
                            rec.projected_pc_preparation_wfh or 0,
                        ],
                        "backgroundColor": "#f26c23"
                    }
                ]
            }

    @api.depends(
        'neo_score_1',
        'neo_score_2',
        'neo_score_3',
        'neo_score_4'
    )
    def _compute_overall_neo_score(self):
        for rec in self:
            scores = [
                rec.neo_score_1,
                rec.neo_score_2,
                rec.neo_score_3,
                rec.neo_score_4,
            ]

            # remove empty values
            scores = [s for s in scores if s]

            if scores:
                rec.overall_neo_score = sum(scores) / len(scores)
            else:
                rec.overall_neo_score = 0.0

    def action_open_dashboard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "helpdesk_dashboard_live",  
            "target": "current",
            "context": {
                "active_id": self.id,
                "view_mode": "readonly",
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            summary_start = vals.get("summary_start")
            summary_end = vals.get("summary_end")

            if summary_start and summary_end:
                existing = self.search([
                    ("create_uid", "=", self.env.user.id),
                    ("summary_start", "=", summary_start),
                    ("summary_end", "=", summary_end),
                ], limit=1)

                if existing:
                    raise UserError(
                        "You have already submitted a dashboard entry for this "
                        "reporting week. Please edit your existing record instead."
                    )

        records = super().create(vals_list)
        records._sync_executive_summary()

        return records

    def write(self, vals):
        for rec in self:
            is_owner = rec.create_uid.id == self.env.user.id
            is_admin = self.env.user.has_group("base.group_system")

            if not (is_owner or is_admin):
                raise UserError(
                    "Only the original creator or an administrator can edit this record."
                )

        result = super().write(vals)
        self._sync_executive_summary()

        return result

    def unlink(self):
        for rec in self:
            is_owner = rec.create_uid.id == self.env.user.id
            is_admin = self.env.user.has_group("base.group_system")

            if not (is_owner or is_admin):
                raise UserError(
                    "Only the original creator or an administrator can delete this record."
                )

        return super().unlink()
    
    def _sync_executive_summary(self):
        for rec in self:
            self.env["it.dashboard.summary.history"].sync_week(
                rec.summary_start,
                rec.summary_end,
            )


    @api.model
    def can_current_user_edit(self):
        return self.env.user.has_group(
            "it_internal_dashboard.group_it_internal_dashboard_developer"
        )
    
    @api.model
    def sync_from_zoho(self):
        SyncLog = self.env["it.zoho.sync.log"].sudo()
        start = time.time()
        creds = False

        try:
            # gets logged instead of crashing invisibly
            creds = self.env["it.zoho.credentials"].sudo().get_active_credentials()
            access_token = creds.get_valid_access_token()

            today = fields.Date.today()
            monday = today - timedelta(days=today.weekday())
            sunday = monday + timedelta(days=6)

            service = ZohoDashboardService(
                access_token,
                creds.zoho_org_id,
                creds.zoho_analytics_workspace_id,
            )

            created_ticket_snapshot = (
                service.get_last_24_hours_created_ticket_snapshot()
            )

            validated_fields = {
                "ticket_count",
                "new_tickets",
                "tickets_from_web",
                "tickets_from_email",
                "tickets_from_phone",
            }

            snapshot = {
                field: created_ticket_snapshot.get(field)
                for field in validated_fields
            }

            if not snapshot:
                raise UserError(
                    "Zoho Desk sync returned no dashboard metrics. "
                    "Check the Zoho API logs and active credentials."
                )

            missing_fields = validated_fields - set(snapshot)

            if missing_fields:
                raise UserError(
                    "Zoho Desk sync is incomplete. "
                    "Missing fields: %s"
                    % ", ".join(sorted(missing_fields))
                )
            
            record = self.sudo().search([
                ("summary_start", "=", monday),
                ("summary_end", "=", sunday),
            ], limit=1)

            if record:
                record.sudo().write(snapshot)
            else:
                snapshot.update({"summary_start": monday, "summary_end": sunday})
                record = self.sudo().create(snapshot)

            SyncLog.create({
                "credentials_id": creds.id,
                "sync_type": "dashboard_sync",
                "status": "success",
                "records_fetched": snapshot["ticket_count"],
                "message": (
                    "Synced Last 24 Hours created-ticket fields: %s. "
                    "period=%s timezone=%s window_start=%s window_end=%s "
                    "department_id=%s raw_channels=%s. "
                    "Unresolved Zoho Overview metrics preserved: "
                    "on_hold_tickets, closed_tickets, backlog_tickets, "
                    "first_response_time, response_time, resolution_time, "
                    "good_rating, okay_rating, bad_rating."
                ) % (
                    ", ".join(sorted(snapshot.keys())),
                    created_ticket_snapshot["period_key"],
                    created_ticket_snapshot["timezone"],
                    created_ticket_snapshot["window_start"].isoformat(),
                    created_ticket_snapshot["window_end"].isoformat(),
                    created_ticket_snapshot["department_id"],
                    json.dumps(
                        created_ticket_snapshot["raw_channel_counts"],
                        sort_keys=True,
                    ),
                ),
                "duration_ms": int((time.time() - start) * 1000),
            })
            return record

        except Exception as exc:
            _logger.error("Zoho dashboard sync failed: %s", exc, exc_info=True)

            try:
                SyncLog.create({
                    "credentials_id": creds.id if creds else False,
                    "sync_type": "dashboard_sync",
                    "status": "error",
                    "message": str(exc),
                    "duration_ms": int((time.time() - start) * 1000),
                })
            except Exception as log_err:
                _logger.error("Additionally failed to write sync log: %s", log_err)

            raise
