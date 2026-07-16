from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import requests
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

ZOHO_TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"


class ZohoCredentials(models.Model):
    _name = "it.zoho.credentials"
    _description = "Zoho OAuth Credentials"
    # Only one active credential set should exist at a time.
    # Having multiple would mean multiple competing refresh cycles.

    name = fields.Char(
        default="Zoho Integration",
        required=True,
    )

    # --- OAuth identifiers ---
    client_id = fields.Char(
        string="Client ID",
        required=True,
        help="From https://api-console.zoho.com — public, but keep it private.",
    )
    client_secret = fields.Char(
        string="Client Secret",
        required=True,
        help="Never expose in logs, JS, or version control.",
    )

    # --- Tokens ---
    # The refresh token almost never expires.
    # You obtain it once via the browser flow, then store it here.
    refresh_token = fields.Char(
        string="Refresh Token",
        help="Obtained once during initial OAuth flow. Guards all future syncs.",
    )
    # The access token expires every 3600 seconds.
    # It is overwritten automatically on every refresh cycle.
    access_token = fields.Char(
        string="Access Token (auto-managed)",
        readonly=True,
    )
    access_token_expiry = fields.Datetime(
        string="Access Token Expires At",
        readonly=True,
    )

    # --- Zoho account identifiers ---
    # These tell you which Zoho organisation to query.
    # Find them at https://desk.zoho.com/api/v1/organizations
    zoho_org_id = fields.Char(string="Zoho Desk Organisation ID")
    zoho_analytics_workspace_id = fields.Char(
        string="Zoho Analytics Workspace ID",
        help="The workspace containing your Analytics reports.",
    )

    # --- Status ---
    is_active = fields.Boolean(default=True)
    last_refresh = fields.Datetime(string="Last Token Refresh", readonly=True)
    last_error = fields.Text(string="Last Error", readonly=True)

    @api.constrains(
        "zoho_org_id",
        "is_active",
    )
    def _check_org_id_when_active(self):
        for rec in self:
            org_id = (
                rec.zoho_org_id or ""
            ).strip()

            if rec.is_active and not org_id:
                raise ValidationError(
                    "Zoho Desk Organisation ID is required "
                    "for active credentials."
                )

    # ---------------------------------------------------------------
    # Token management
    # ---------------------------------------------------------------

    def _is_token_valid(self):
        """Return True if the stored access token is still usable."""
        self.ensure_one()
        if not self.access_token or not self.access_token_expiry:
            return False
        # Give a 60-second buffer so we never send an about-to-expire token.
        return datetime.now() < (
            self.access_token_expiry - timedelta(seconds=60)
        )

    def get_valid_access_token(self):
        """
        Return a usable access token.
        Refreshes automatically if the current one is expired or missing.
        Call this from every service method that needs to hit Zoho.
        """
        self.ensure_one()
        if not self._is_token_valid():
            self._refresh_access_token()
        return self.access_token

    def _refresh_access_token(self):
        """
        Exchange the refresh token for a new access token.
        Zoho endpoint: POST https://accounts.zoho.com/oauth/v2/token
        """
        self.ensure_one()
        if not self.refresh_token:
            raise UserError(
                "No refresh token stored. "
                "Please complete the initial OAuth connection first."
            )

        try:
            response = requests.post(
                ZOHO_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                },
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                raise UserError(
                    f"Zoho token refresh failed: {data['error']}"
                )

            self.sudo().write({
                "access_token": data["access_token"],
                "access_token_expiry": datetime.now() + timedelta(
                    seconds=data.get("expires_in", 3600)
                ),
                "last_refresh": datetime.now(),
                "last_error": False,
            })

        except requests.exceptions.RequestException as exc:
            error_msg = f"Network error during token refresh: {exc}"
            _logger.error(error_msg)
            self.sudo().write({"last_error": error_msg})
            raise UserError(error_msg)

    @api.model
    def get_active_credentials(self):
        """
        Convenience method: return the single active credential record.
        Raises a clear UserError if nothing is configured.
        """
        creds = self.search([("is_active", "=", True)], limit=1)
        if not creds:
            raise UserError(
                "No active Zoho credentials found. "
                "Please configure them under Settings → Zoho Integration."
            )
        return creds