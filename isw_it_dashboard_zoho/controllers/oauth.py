import logging
from datetime import timedelta

import requests

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class ZohoOAuthController(http.Controller):
    @http.route(
        "/it-dashboard/zoho/oauth/callback",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def zoho_oauth_callback(self, code=None, state=None, error=None, **kwargs):
        config = request.env["ir.config_parameter"].sudo()
        settings_action = request.env.ref(
            "isw_it_dashboard_zoho.action_zoho_desk_settings",
            raise_if_not_found=False,
        )
        redirect_url = f"/web#action={settings_action.id}" if settings_action else "/web"

        if error:
            config.set_param("isw_it_dashboard_zoho.connection_status", "error")
            config.set_param("isw_it_dashboard_zoho.last_error", f"Authorization denied: {error}")
            return request.redirect(redirect_url)

        expected_state = config.get_param("isw_it_dashboard_zoho.oauth_state") or ""
        state_created_raw = config.get_param("isw_it_dashboard_zoho.oauth_state_created_at") or ""
        state_created = fields.Datetime.to_datetime(state_created_raw) if state_created_raw else False
        state_expired = not state_created or state_created < fields.Datetime.now() - timedelta(minutes=10)
        if not state or state != expected_state or state_expired:
            config.set_param("isw_it_dashboard_zoho.connection_status", "error")
            config.set_param("isw_it_dashboard_zoho.last_error", "Invalid or expired OAuth state.")
            return request.redirect(redirect_url)

        if not code:
            config.set_param("isw_it_dashboard_zoho.connection_status", "error")
            config.set_param("isw_it_dashboard_zoho.last_error", "Zoho did not return an authorization code.")
            return request.redirect(redirect_url)

        accounts_url = (config.get_param("isw_it_dashboard_zoho.accounts_url") or "https://accounts.zoho.com").strip().rstrip("/")
        client_id = (config.get_param("isw_it_dashboard_zoho.client_id") or "").strip()
        client_secret = (config.get_param("isw_it_dashboard_zoho.client_secret") or "").strip()
        redirect_uri = (config.get_param("isw_it_dashboard_zoho.redirect_uri") or "").strip()

        try:
            response = requests.post(
                f"{accounts_url}/oauth/v2/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
                timeout=30,
            )
            try:
                payload = response.json()
            except ValueError:
                payload = {}

            if not response.ok:
                safe_error = payload.get("error") or payload.get("message") or f"HTTP {response.status_code}"
                _logger.error("Zoho OAuth code exchange failed. status=%s error=%s", response.status_code, safe_error)
                config.set_param("isw_it_dashboard_zoho.connection_status", "error")
                config.set_param("isw_it_dashboard_zoho.last_error", f"OAuth code exchange failed: {safe_error}")
                return request.redirect(redirect_url)

            refresh_token = payload.get("refresh_token")
            access_token = payload.get("access_token")
            if not refresh_token:
                config.set_param("isw_it_dashboard_zoho.connection_status", "error")
                config.set_param(
                    "isw_it_dashboard_zoho.last_error",
                    "Zoho did not return a refresh token. Re-authorize with offline access and consent.",
                )
                return request.redirect(redirect_url)

            expires_in = int(payload.get("expires_in") or 3600)
            expires_at = fields.Datetime.now() + timedelta(seconds=expires_in)
            config.set_param("isw_it_dashboard_zoho.refresh_token", refresh_token)
            config.set_param("isw_it_dashboard_zoho.access_token", access_token or "")
            config.set_param("isw_it_dashboard_zoho.access_token_expires_at", fields.Datetime.to_string(expires_at))
            config.set_param("isw_it_dashboard_zoho.connection_status", "connected")
            config.set_param("isw_it_dashboard_zoho.authorized_at", fields.Datetime.to_string(fields.Datetime.now()))
            config.set_param("isw_it_dashboard_zoho.authorized_by", request.env.user.display_name)
            config.set_param("isw_it_dashboard_zoho.last_error", "")
            config.set_param("isw_it_dashboard_zoho.oauth_state", "")
            config.set_param("isw_it_dashboard_zoho.oauth_state_created_at", "")
            return request.redirect(redirect_url)
        except requests.RequestException:
            _logger.exception("Unable to connect to Zoho OAuth during code exchange.")
            config.set_param("isw_it_dashboard_zoho.connection_status", "error")
            config.set_param("isw_it_dashboard_zoho.last_error", "Unable to connect to the Zoho OAuth service.")
            return request.redirect(redirect_url)
