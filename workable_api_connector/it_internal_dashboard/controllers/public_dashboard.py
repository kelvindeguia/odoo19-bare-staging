"""
public_dashboard.py
-------------------
Public HTTP and JSON controllers for the dashboard workspace.

All routes are auth="public" — no Odoo login required.
Every route validates the share token before doing anything.
Invalid/expired/revoked tokens always return 404, never 403.
"""
import logging
from odoo import http
from odoo.http import request
from ..services.dashboard_publication_service import DashboardPublicationService

_logger = logging.getLogger(__name__)


class PublicDashboardController(http.Controller):

    # ----------------------------------------------------------------
    # Token validation — called at the top of every route
    # ----------------------------------------------------------------

    def _get_publication_or_404(self, token: str):
        """
        Returns the publication record if the token is valid,
        active, and not expired. Returns None otherwise.

        Always 404, never 403:
        - 403 reveals the resource exists (information leak)
        - 404 reveals nothing
        """
        if not token:
            return None

        pub = (
            request.env["it.dashboard.publication"]
            .sudo()
            ._validate_token(token)
        )

        if not pub:
            return None

        pub._record_access()
        return pub

    # ----------------------------------------------------------------
    # Route 1 — HTML shell (browser navigates here first)
    # ----------------------------------------------------------------

    @http.route(
        "/it-internal-dashboard-test2/<string:token>",
        type="http",            # returns HTML
        auth="public",          # no Odoo login required
        website=True,           # uses website.layout
        sitemap=False,          # never indexed by search engines
        methods=["GET"],
        csrf=False,
    )
    def public_dashboard_workspace(self, token, **kwargs):
        pub = self._get_publication_or_404(token)
        if not pub:
            return request.not_found()

        default_start, default_end = pub._default_window()
        return request.render(
            "it_internal_dashboard_test2.public_dashboard_workspace",
            {
                "token": token,
                "publication": pub,
                "week_label": f"{default_start.strftime('%B %d')} – {default_end.strftime('%B %d, %Y')}",
                "allow_print": pub.allow_print,
            },
        )

    # ----------------------------------------------------------------
    # Route 2 — Navigation list (JSON)
    # FIX: was type="jsonrpc" — not a valid Odoo route type
    # ----------------------------------------------------------------

    @http.route(
        "/it-internal-dashboard-test2/<string:token>/nav",
        type="json",            # ← FIXED: was "jsonrpc" (invalid)
        auth="public",
        sitemap=False,
        methods=["POST"],
        csrf=False,
    )
    def public_dashboard_nav(self, token, **kwargs):
        pub = self._get_publication_or_404(token)
        if not pub:
            return {"error": "not_found"}

        default_start, default_end = pub._default_window()
        service = DashboardPublicationService(request.env, pub)
        return {
            "nav": service.get_navigation(),
            "week_label": f"{default_start.strftime('%B %d')} – {default_end.strftime('%B %d, %Y')}",
            "allow_print": pub.allow_print,
            "default_start_date": default_start.isoformat(),
            "default_end_date": default_end.isoformat(),
        }

    # ----------------------------------------------------------------
    # Route 3 — Section data (JSON)
    # FIX: was type="jsonrpc" — not a valid Odoo route type
    # ----------------------------------------------------------------

    @http.route(
        "/it-internal-dashboard-test2/<string:token>/data",
        type="json",            # ← FIXED: was "jsonrpc" (invalid)
        auth="public",
        sitemap=False,
        methods=["POST"],
        csrf=False,
    )
    def public_dashboard_data(self, token, section=None, start_date=None, end_date=None, **kwargs):
        """
        Now accepts start_date/end_date — but every value is validated
        against the publication's guardrails before being used. Invalid
        or out-of-bounds ranges are rejected, never silently widened.
        """
        pub = self._get_publication_or_404(token)
        if not pub:
            return {"error": "not_found"}

        if not section:
            return {"error": "section_required"}

        if start_date and end_date:
            validated = pub._validate_date_range(start_date, end_date)
            if not validated:
                return {"error": "invalid_date_range"}
            window_start, window_end = validated
        else:
            window_start, window_end = pub._default_window()

        service = DashboardPublicationService(request.env, pub, window_start, window_end)
        return service.get_full_payload(section)

    # ----------------------------------------------------------------
    # Route 4 — Secure image proxy (HTTP)
    # ----------------------------------------------------------------

    @http.route(
        "/it-internal-dashboard-test2/<string:token>/image",
        type="http",
        auth="public",
        sitemap=False,
        methods=["GET"],
        csrf=False,
    )
    def public_dashboard_image(self, token, section=None, field=None, start_date=None, end_date=None, **kwargs):
        pub = self._get_publication_or_404(token)
        if not pub:
            return request.not_found()

        allowed = {
            "helpdesk": {
                "model": "it.helpdesk.dashboard",
                "fields": ["lighthouse_report", "neo_satisfaction_score", "new_tickets", "on_hold_tickets", "closed_tickets", "backlog_tickets"],
            },
        }
        config = allowed.get(section)
        if not config or field not in config["fields"]:
            _logger.warning("Public image blocked — non-whitelisted section/field: %s/%s", section, field)
            return request.not_found()

        if start_date and end_date:
            validated = pub._validate_date_range(start_date, end_date)
            if validated:
                window_start, window_end = validated
            else:
                _logger.warning(
                    "Invalid public dashboard image date range for token %s: %s - %s",
                    token,
                    start_date,
                    end_date,
                )
                window_start, window_end = pub._default_window()
        else:
            window_start, window_end = pub._default_window()

        record = (
            request.env[config["model"]]
            .sudo()
            .search(
                [
                    ("summary_start", "<=", window_end),
                    ("summary_end", ">=", window_start),
                ],
                order="summary_start desc, id desc",
                limit=1,
            )
        )

        if not record or not record[field]:
            return request.not_found()

        return request.env["ir.binary"]._get_image_stream_from(record, field_name=field).get_response()
