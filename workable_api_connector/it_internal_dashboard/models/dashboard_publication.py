"""
dashboard_publication.py
------------------------
Represents a published dashboard package.

One record = one secure, reusable share link.

When an internal user clicks "Generate Share Link", Odoo creates
one of these records and returns the URL. External users never
interact with this model directly — the controller reads it on
their behalf.
"""
import secrets
import hashlib
from datetime import date, datetime, timedelta

from odoo import models, fields, api
from odoo.exceptions import UserError


class DashboardPublication(models.Model):
    _name = "it.dashboard.publication"
    _description = "Dashboard Publication (Public Share Link)"
    _order = "publication_date desc"

    name = fields.Char(
        compute="_compute_name",
        store=True,
    )

    share_token = fields.Char(
        string="Share Token",
        readonly=True,
        index=True,
        copy=False,
    )

    share_url = fields.Char(
        string="Share URL",
        compute="_compute_share_url",
    )

    publication_date = fields.Datetime(
        default=fields.Datetime.now,
        readonly=True,
    )

    expires_at = fields.Datetime(
        string="Expires At",
        help="Leave empty for a link that never expires.",
    )

    active = fields.Boolean(
        default=True,
        help="Uncheck to revoke this link immediately.",
    )

    include_helpdesk = fields.Boolean(default=True)
    include_infra = fields.Boolean(default=True)
    include_devops = fields.Boolean(default=True)
    include_compliance = fields.Boolean(default=True)
    include_management = fields.Boolean(default=True)
    include_executive_summary = fields.Boolean(default=True)

    allow_print = fields.Boolean(default=True)

    created_by = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        readonly=True,
    )

    last_access = fields.Datetime(readonly=True)
    access_count = fields.Integer(readonly=True, default=0)
    is_expired = fields.Boolean(compute="_compute_is_expired", string="Expired")

    # ----------------------------------------------------------------
    # NEW: date-range guardrails, replacing the old fixed week_start/end.
    # These bound what an anonymous caller can request via start_date/
    # end_date on /it-internal-dashboard-test2/<token>/data — not what data actually gets
    # returned. The actual range is chosen by the external user in the
    # UI; these fields just cap how far they can roam.
    # ----------------------------------------------------------------

    max_history_days = fields.Integer(
        string="Max Days Back",
        default=90,
        help=(
            "External users cannot request a start_date older than this "
            "many days before today. Leave 0/blank for unrestricted "
            "(not recommended — allows browsing the entire dataset history)."
        ),
    )
    max_future_days = fields.Integer(
        string="Max Days Forward",
        default=14,
        help=(
            "External users cannot request an end_date more than this "
            "many days after today (covers 'projected next week' views)."
        ),
    )
    max_range_span_days = fields.Integer(
        string="Max Range Span (days)",
        default=31,
        help=(
            "Maximum number of days a single filtered view may span "
            "(start_date to end_date). Prevents oversized/expensive queries."
        ),
    )

    _sql_constraints = [
        ("unique_share_token", "UNIQUE(share_token)", "Share token must be unique."),
    ]

    @api.depends("publication_date", "include_executive_summary")
    def _compute_name(self):
        for rec in self:
            if rec.publication_date:
                rec.name = f"Public Dashboard Link — created {rec.publication_date.strftime('%b %d, %Y')}"
            else:
                rec.name = "Public Dashboard Link"

    @api.depends("share_token")
    def _compute_share_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param(
            "web.base.url", "https://dashboard-staging.isw-connect.com"
        )
        for rec in self:
            rec.share_url = f"{base_url}/it-internal-dashboard-test2/{rec.share_token}" if rec.share_token else ""

    def _compute_is_expired(self):
        now = datetime.now()
        for rec in self:
            rec.is_expired = bool(rec.expires_at and rec.expires_at < now)

    @api.model
    def _generate_token(self) -> str:
        return secrets.token_hex(32)

    @api.model
    def action_generate_publication(
        self,
        expires_days=None,
        sections=None,
        max_history_days=90,
        max_future_days=14,
        max_range_span_days=31,
    ):
        """
        Create a new persistent publication record and return the share URL.
        No week_start/week_end — this link is not scoped to one week.
        Date filtering happens per-request, bounded by the guardrails below.
        """
        sections = sections or {}

        expires_at = None
        if expires_days:
            expires_at = datetime.now() + timedelta(days=expires_days)

        publication = self.create({
            "share_token": self._generate_token(),
            "expires_at": expires_at,
            "include_helpdesk": sections.get("helpdesk", True),
            "include_infra": sections.get("infra", True),
            "include_devops": sections.get("devops", True),
            "include_compliance": sections.get("compliance", True),
            "include_management": sections.get("management", True),
            "include_executive_summary": sections.get("executive_summary", True),
            "max_history_days": max_history_days,
            "max_future_days": max_future_days,
            "max_range_span_days": max_range_span_days,
        })

        return {
            "publication_id": publication.id,
            "share_url": publication.share_url,
            "token": publication.share_token,
        }

    def action_revoke(self):
        self.write({"active": False})

    def action_regenerate_token(self):
        self.write({"share_token": self._generate_token()})

    def _validate_token(self, token: str) -> "DashboardPublication":
        if not token or len(token) != 64:
            return self.browse()
        record = self.search([("share_token", "=", token), ("active", "=", True)], limit=1)
        if not record or record.is_expired:
            return self.browse()
        return record

    def _record_access(self):
        self.sudo().write({
            "last_access": datetime.now(),
            "access_count": self.access_count + 1,
        })

    # ----------------------------------------------------------------
    # NEW: server-side date range validation.
    # Every incoming start_date/end_date from the public controller
    # MUST pass through here before being used to query anything.
    # Returns (start_date, end_date) as date objects on success,
    # or None on failure — caller decides how to respond (fallback
    # to default window, or reject the request).
    # ----------------------------------------------------------------

    def _default_window(self):
        """Latest saved reporting week, falling back to the current public window."""
        latest = self._latest_dashboard_window()
        if latest:
            return latest

        today = date.today()
        monday = today - timedelta(days=today.weekday())
        window_end = monday + timedelta(days=10)
        return monday, window_end

    def _latest_dashboard_window(self):
        self.ensure_one()

        section_models = [
            (self.include_helpdesk, "it.helpdesk.dashboard"),
            (self.include_infra, "it.infra.dashboard"),
            (self.include_devops, "it.devops.dashboard"),
            (self.include_compliance, "it.compliance.dashboard"),
            (self.include_management, "it.management.dashboard"),
        ]

        latest_record = None
        for included, model in section_models:
            if not included:
                continue
            record = self.env[model].sudo().search(
                [("summary_start", "!=", False), ("summary_end", "!=", False)],
                order="summary_start desc, id desc",
                limit=1,
            )
            if record and (
                not latest_record
                or record.summary_start > latest_record.summary_start
            ):
                latest_record = record

        if latest_record:
            return latest_record.summary_start, latest_record.summary_end
        return None

    def _validate_date_range(self, start_date, end_date):
        self.ensure_one()

        start = self._safe_parse_date(start_date)
        end = self._safe_parse_date(end_date)

        if not start or not end:
            return None
        if end < start:
            return None

        today = date.today()

        span_days = (end - start).days + 1
        if self.max_range_span_days and span_days > self.max_range_span_days:
            return None

        if self.max_history_days:
            earliest_allowed = today - timedelta(days=self.max_history_days)
            if start < earliest_allowed:
                return None

        if self.max_future_days:
            latest_allowed = today + timedelta(days=self.max_future_days)
            if end > latest_allowed:
                return None

        return start, end

    @staticmethod
    def _safe_parse_date(value):
        if not value:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value)[:10])
        except (ValueError, TypeError):
            return None
