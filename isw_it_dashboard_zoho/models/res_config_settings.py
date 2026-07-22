from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    zoho_desk_enabled = fields.Boolean(config_parameter="isw_it_dashboard_zoho.enabled")
    zoho_desk_api_base = fields.Char(config_parameter="isw_it_dashboard_zoho.api_base", default="https://desk.zoho.com/api/v1")
    zoho_accounts_url = fields.Char(config_parameter="isw_it_dashboard_zoho.accounts_url", default="https://accounts.zoho.com")
    zoho_org_id = fields.Char(config_parameter="isw_it_dashboard_zoho.org_id")
    zoho_client_id = fields.Char(config_parameter="isw_it_dashboard_zoho.client_id")
    zoho_client_secret = fields.Char(config_parameter="isw_it_dashboard_zoho.client_secret")
    zoho_refresh_token = fields.Char(config_parameter="isw_it_dashboard_zoho.refresh_token")
    zoho_webhook_secret = fields.Char(config_parameter="isw_it_dashboard_zoho.webhook_secret")
    zoho_department_ids = fields.Char(config_parameter="isw_it_dashboard_zoho.department_ids", help="Optional comma-separated Zoho Desk department IDs.")
