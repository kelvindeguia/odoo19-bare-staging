import secrets
from urllib.parse import urlencode

from odoo import _, fields, models
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    zoho_desk_enabled = fields.Boolean(
        string="Enable Zoho Desk Synchronization",
        config_parameter="isw_it_dashboard_zoho.enabled",
    )
    zoho_desk_api_base = fields.Char(
        string="Zoho Desk API Base URL",
        config_parameter="isw_it_dashboard_zoho.api_base",
        default="https://desk.zoho.com/api/v1",
    )
    zoho_accounts_url = fields.Char(
        string="Zoho Accounts URL",
        config_parameter="isw_it_dashboard_zoho.accounts_url",
        default="https://accounts.zoho.com",
    )
    zoho_org_id = fields.Char(
        string="Organization ID",
        config_parameter="isw_it_dashboard_zoho.org_id",
    )
    zoho_client_id = fields.Char(
        string="OAuth Client ID",
        config_parameter="isw_it_dashboard_zoho.client_id",
    )
    zoho_client_secret = fields.Char(
        string="OAuth Client Secret",
        config_parameter="isw_it_dashboard_zoho.client_secret",
    )
    zoho_redirect_uri = fields.Char(
        string="OAuth Redirect URI",
        config_parameter="isw_it_dashboard_zoho.redirect_uri",
    )
    zoho_oauth_scopes = fields.Char(
        string="OAuth Scopes",
        config_parameter="isw_it_dashboard_zoho.oauth_scopes",
        default="Desk.tickets.READ,Desk.settings.READ",
    )
    zoho_refresh_token = fields.Char(
        string="OAuth Refresh Token",
        config_parameter="isw_it_dashboard_zoho.refresh_token",
        readonly=True,
    )
    zoho_webhook_secret = fields.Char(
        string="Webhook Secret",
        config_parameter="isw_it_dashboard_zoho.webhook_secret",
    )
    zoho_department_ids = fields.Char(
        string="Department IDs",
        config_parameter="isw_it_dashboard_zoho.department_ids",
        help="Optional comma-separated Zoho Desk department IDs.",
    )
    zoho_sync_lookback_days = fields.Integer(
        string="Synchronization Lookback (Days)",
        config_parameter="isw_it_dashboard_zoho.sync_lookback_days",
        default=7,
    )
    zoho_connection_status = fields.Char(
        string="Connection Status",
        config_parameter="isw_it_dashboard_zoho.connection_status",
        readonly=True,
    )
    zoho_authorized_at = fields.Datetime(
        string="Authorized At",
        config_parameter="isw_it_dashboard_zoho.authorized_at",
        readonly=True,
    )
    zoho_authorized_by = fields.Char(
        string="Authorized By",
        config_parameter="isw_it_dashboard_zoho.authorized_by",
        readonly=True,
    )
    zoho_last_sync_at = fields.Datetime(
        string="Last Successful Sync",
        config_parameter="isw_it_dashboard_zoho.last_sync_at",
        readonly=True,
    )
    zoho_last_error = fields.Text(
        string="Last Integration Error",
        config_parameter="isw_it_dashboard_zoho.last_error",
        readonly=True,
    )

    def _save_current_settings(self):
        self.ensure_one()
        self.set_values()

    def action_authorize_zoho(self):
        self.ensure_one()
        self._save_current_settings()

        accounts_url = (self.zoho_accounts_url or "").strip().rstrip("/")
        client_id = (self.zoho_client_id or "").strip()
        redirect_uri = (self.zoho_redirect_uri or "").strip()
        scopes = (self.zoho_oauth_scopes or "").strip()

        missing = []
        if not accounts_url:
            missing.append(_("Zoho Accounts URL"))
        if not client_id:
            missing.append(_("OAuth Client ID"))
        if not self.zoho_client_secret:
            missing.append(_("OAuth Client Secret"))
        if not redirect_uri:
            missing.append(_("OAuth Redirect URI"))
        if not scopes:
            missing.append(_("OAuth Scopes"))
        if missing:
            raise UserError(_("Complete these fields first: %s") % ", ".join(missing))

        state = secrets.token_urlsafe(32)
        config = self.env["ir.config_parameter"].sudo()
        config.set_param("isw_it_dashboard_zoho.oauth_state", state)
        config.set_param(
            "isw_it_dashboard_zoho.oauth_state_created_at",
            fields.Datetime.to_string(fields.Datetime.now()),
        )

        query = urlencode(
            {
                "scope": scopes,
                "client_id": client_id,
                "response_type": "code",
                "access_type": "offline",
                "prompt": "consent",
                "redirect_uri": redirect_uri,
                "state": state,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": f"{accounts_url}/oauth/v2/auth?{query}",
            "target": "self",
        }

    def action_test_zoho_connection(self):
        self.ensure_one()
        self._save_current_settings()
        result = self.env["it.zoho.ticket"].sudo().test_connection()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Zoho Desk Connection"),
                "message": result,
                "type": "success",
                "sticky": False,
            },
        }

    def action_sync_zoho_now(self):
        self.ensure_one()
        self._save_current_settings()
        result = self.env["it.zoho.ticket"].sudo().sync_tickets(raise_on_error=True)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Zoho Desk Synchronization"),
                "message": _(
                    "Received %(received)s, created %(created)s, updated %(updated)s, failed %(failed)s."
                )
                % result,
                "type": "warning" if result["failed"] else "success",
                "sticky": result["failed"] > 0,
            },
        }

    def action_disconnect_zoho(self):
        self.ensure_one()
        config = self.env["ir.config_parameter"].sudo()
        for key in (
            "refresh_token",
            "access_token",
            "access_token_expires_at",
            "oauth_state",
            "oauth_state_created_at",
            "authorized_at",
            "authorized_by",
        ):
            config.set_param(f"isw_it_dashboard_zoho.{key}", "")
        config.set_param("isw_it_dashboard_zoho.connection_status", "disconnected")
        config.set_param("isw_it_dashboard_zoho.last_error", "")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Zoho Desk"),
                "message": _("The Zoho authorization stored in Odoo was removed."),
                "type": "info",
                "sticky": False,
            },
        }
