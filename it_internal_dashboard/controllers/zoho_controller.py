"""
zoho_controller.py
------------------
Three responsibilities:
1. /zoho/connect    — redirect the admin's browser to Zoho's login page
2. /zoho/callback   — receive the one-time code from Zoho, exchange for tokens
3. /zoho/sync       — trigger a manual sync, called from OWL or ir.cron
4. /zoho/status     — return current sync status for the OWL dashboard
"""
import logging
from odoo import http
from odoo.http import request
from werkzeug.utils import redirect as werkzeug_redirect
from ..services.zoho_auth import build_auth_url, exchange_code_for_tokens

_logger = logging.getLogger(__name__)

REDIRECT_URI_PATH = "/zoho/callback"


class ZohoController(http.Controller):

    @http.route("/zoho/connect", type="http", auth="user", methods=["GET"])
    def zoho_connect(self, **kwargs):
        """
        Step 1 of OAuth.
        Admin visits /zoho/connect in their browser.
        We redirect them to Zoho's login page.
        """
        creds = request.env["it.zoho.credentials"].sudo().get_active_credentials()
        base_url = request.env["ir.config_parameter"].sudo().get_param("web.base.url")
        redirect_uri = f"{base_url}{REDIRECT_URI_PATH}"

        auth_url = build_auth_url(creds.client_id, redirect_uri)

        _logger.info("=== FULL ZOHO CONNECT URL: %s ===", auth_url)

        return werkzeug_redirect(auth_url, code=302)

    @http.route("/zoho/callback", type="http", auth="user", methods=["GET"])
    def zoho_callback(self, code=None, error=None, **kwargs):
        """
        Step 2 of OAuth.
        Zoho redirects here after the user approves.
        We exchange the code for tokens and store them.
        """
        if error:
            return request.make_response(
                f"<h1>Zoho OAuth Error: {error}</h1>",
                headers=[("Content-Type", "text/html")],
            )

        if not code:
            return request.make_response(
                "<h1>No code received from Zoho.</h1>",
                headers=[("Content-Type", "text/html")],
            )

        try:
            creds = (
                request.env["it.zoho.credentials"].sudo().get_active_credentials()
            )
            base_url = (
                request.env["ir.config_parameter"]
                .sudo()
                .get_param("web.base.url")
            )
            redirect_uri = f"{base_url}{REDIRECT_URI_PATH}"

            tokens = exchange_code_for_tokens(
                creds.client_id,
                creds.client_secret,
                redirect_uri,
                code,
            )

            creds.sudo().write({
                "refresh_token": tokens["refresh_token"],
                "access_token": tokens["access_token"],
            })

            return request.make_response(
                "<h1>Zoho connected successfully. You can close this tab.</h1>",
                headers=[("Content-Type", "text/html")],
            )

        except Exception as exc:
            _logger.error("Zoho callback error: %s", exc)
            return request.make_response(
                f"<h1>Connection failed: {exc}</h1>",
                headers=[("Content-Type", "text/html")],
            )

    @http.route("/zoho/sync", type="jsonrpc", auth="user", methods=["POST"])
    def zoho_sync(self, **kwargs):
        """
        Manual sync trigger.
        Called from OWL when the user clicks "Sync from Zoho".
        Also called by ir.cron for automatic syncs.
        """
        try:
            request.env["it.helpdesk.dashboard"].sudo().sync_from_zoho()
            return {"status": "success", "message": "Sync completed."}
        except Exception as exc:
            _logger.error("Manual sync error: %s", exc)
            return {"status": "error", "message": str(exc)}

    @http.route("/zoho/status", type="jsonrpc", auth="user", methods=["POST"])
    def zoho_status(self, **kwargs):
        """
        Returns the current integration status for the OWL settings panel.
        """
        creds = (
            request.env["it.zoho.credentials"]
            .sudo()
            .search([("is_active", "=", True)], limit=1)
        )
        if not creds:
            return {"connected": False}

        return {
            "connected": bool(creds.refresh_token),
            "last_refresh": str(creds.last_refresh or ""),
            "last_error": creds.last_error or "",
        }