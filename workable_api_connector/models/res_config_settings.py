from odoo import fields, models, _
from odoo.exceptions import UserError

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    workable_api_token = fields.Char(
        string='Workable API Token',
        config_parameter='workable.api_token'
    )
    workable_subdomain = fields.Char(
        string='Workable Subdomain',
        help='Your Workable account subdomain, e.g. "mycompany" from mycompany.workable.com',
        config_parameter='workable.subdomain'
    )

    workable_webhook_secret = fields.Char(
        string="Webhook Secret",
        help="Shared secret used to validate inbound Workable webhook requests.",
        config_parameter="workable.webhook_secret",
    )
    workable_webhook_auto_process = fields.Boolean(
        string="Auto-process Webhook Immediately",
        help="If enabled, Odoo will process the webhook during the HTTP request. For production, leave disabled and use the queue cron.",
        config_parameter="workable.webhook_auto_process",
        default=False,
    )
    workable_outbound_sync_enabled = fields.Boolean(
        string="Enable Odoo to Workable Outbound Sync",
        help="Safe feature flag for future Odoo-to-Workable API updates. Keep disabled until field-level rules are finalized.",
        config_parameter="workable.outbound_sync_enabled",
        default=False,
    )
    workable_public_webhook_url = fields.Char(
        string="Public Webhook URL",
        compute="_compute_workable_public_webhook_url",
        readonly=True,
    )
    workable_candidate_hired_webhook_url = fields.Char(
        string="Candidate Hired Webhook URL",
        compute="_compute_workable_public_webhook_url",
        readonly=True,
    )

    def _compute_workable_public_webhook_url(self):
        ICP = self.env["ir.config_parameter"].sudo()
        base_url = ICP.get_param("web.base.url") or ""
        secret = ICP.get_param("workable.webhook_secret") or ""

        public_url = "%s/workable/webhook" % base_url.rstrip("/")
        secret_url = public_url
        if secret:
            secret_url = "%s?secret=%s" % (public_url, secret)

        for rec in self:
            rec.workable_public_webhook_url = public_url
            rec.workable_candidate_hired_webhook_url = secret_url

    def action_register_candidate_moved_hired_webhook(self):
        self.ensure_one()

        target_url = self.workable_candidate_hired_webhook_url or self.workable_public_webhook_url
        if not target_url:
            raise UserError(_("The Odoo public webhook URL is not available. Please configure web.base.url first."))

        payload = {
            "target": target_url,
            "event": "candidate_moved",
            "args": {
                "stage": "hired",
            },
        }

        try:
            response = self.env["workable.candidate"].sudo()._workable_request(
                "POST",
                "/subscriptions",
                json_payload=payload,
            )
        except Exception as exc:
            raise UserError(_("Could not register the Workable candidate_moved/hired webhook subscription: %s") % exc)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Workable Webhook Registered"),
                "message": _("The candidate_moved webhook filtered to the Hired stage was registered successfully."),
                "type": "success",
                "sticky": False,
            },
        }
