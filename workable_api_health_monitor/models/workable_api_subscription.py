import json
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


WORKABLE_EVENTS = [
    ("candidate_created", "Candidate Created"),
    ("candidate_deleted", "Candidate Deleted"),
    ("candidate_moved", "Candidate Moved"),
    ("employee_created", "Employee Created"),
    ("employee_updated", "Employee Updated"),
    ("employee_published", "Employee Published"),
    ("job_deleted", "Job Deleted"),
    ("onboarding_completed", "Onboarding Completed"),
    ("timeoff_updated", "Time Off Updated"),
]


class WorkableApiSubscription(models.Model):
    _name = "workable.api.subscription"
    _description = "Workable API Subscription"
    _inherit = ["mail.thread"]
    _order = "account_id, event_type"

    name = fields.Char(compute="_compute_name", store=True)
    active = fields.Boolean(default=True, tracking=True)
    account_id = fields.Many2one(
        "workable.api.account",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(related="account_id.company_id", store=True)
    event_type = fields.Selection(WORKABLE_EVENTS, required=True, tracking=True)
    use_account_webhook_url = fields.Boolean(default=True)
    target_url = fields.Char(
        compute="_compute_target_url",
        inverse="_inverse_target_url",
        store=True,
        readonly=False,
        required=True,
    )
    custom_target_url = fields.Char()
    job_shortcode = fields.Char(
        help="Optional candidate-event filter passed through Workable subscription args."
    )
    stage_slug = fields.Char(
        help="Optional candidate-event filter passed through Workable subscription args."
    )
    auto_register = fields.Boolean(default=False)
    workable_subscription_id = fields.Char(readonly=True, copy=False, index=True)
    remote_target_url = fields.Char(readonly=True)
    remote_event_type = fields.Char(readonly=True)
    remote_payload = fields.Text(readonly=True)

    health_status = fields.Selection(
        [
            ("not_checked", "Not Checked"),
            ("healthy", "Healthy"),
            ("missing", "Missing"),
            ("duplicate", "Duplicate"),
            ("url_mismatch", "Target URL Mismatch"),
            ("event_mismatch", "Event Mismatch"),
            ("webhook_stale", "Webhook Stale"),
            ("api_error", "API Error"),
        ],
        required=True,
        default="not_checked",
        readonly=True,
        tracking=True,
    )
    health_message = fields.Text(readonly=True)
    last_check_date = fields.Datetime(readonly=True)
    last_webhook_received = fields.Datetime(readonly=True)
    last_webhook_signature_valid = fields.Boolean(readonly=True)

    @api.depends("account_id.name", "event_type")
    def _compute_name(self):
        event_labels = dict(WORKABLE_EVENTS)
        for record in self:
            record.name = "%s - %s" % (
                record.account_id.name or _("Account"),
                event_labels.get(record.event_type, record.event_type or _("Event")),
            )

    @api.depends(
        "use_account_webhook_url", "account_id.webhook_url", "custom_target_url"
    )
    def _compute_target_url(self):
        for record in self:
            record.target_url = (
                record.account_id.webhook_url
                if record.use_account_webhook_url
                else record.custom_target_url
            )

    def _inverse_target_url(self):
        for record in self:
            if not record.use_account_webhook_url:
                record.custom_target_url = record.target_url

    @api.constrains("target_url")
    def _check_target_url(self):
        for record in self:
            if record.target_url and not record.target_url.startswith(("https://", "http://")):
                raise ValidationError(_("The webhook target must be an HTTP or HTTPS URL."))

    @api.constrains("account_id", "event_type", "job_shortcode", "stage_slug")
    def _check_duplicate_configuration(self):
        for record in self:
            duplicate = self.search_count(
                [
                    ("id", "!=", record.id),
                    ("account_id", "=", record.account_id.id),
                    ("event_type", "=", record.event_type),
                    ("job_shortcode", "=", record.job_shortcode or False),
                    ("stage_slug", "=", record.stage_slug or False),
                    ("active", "=", True),
                ]
            )
            if duplicate:
                raise ValidationError(
                    _("An active subscription with the same account, event, job, and stage already exists.")
                )

    def _subscription_args(self):
        self.ensure_one()
        args = {}
        if self.job_shortcode:
            args["job"] = self.job_shortcode
        if self.stage_slug:
            args["stage"] = self.stage_slug
        return args

    def action_register(self):
        for subscription in self:
            if not subscription.target_url:
                raise UserError(_("A webhook target URL is required."))
            payload = {
                "target": subscription.target_url,
                "event": subscription.event_type,
            }
            args = subscription._subscription_args()
            if args:
                payload["args"] = args
            response, response_payload, elapsed_ms = subscription.account_id._api_request(
                "POST", "subscriptions", payload
            )
            status_code = response.status_code if response else 0
            if response is not None and response.status_code in (200, 201):
                remote_id = (
                    response_payload.get("id")
                    or response_payload.get("subscription_id")
                    or (response_payload.get("subscription") or {}).get("id")
                )
                subscription.write(
                    {
                        "workable_subscription_id": str(remote_id or ""),
                        "health_status": "healthy",
                        "health_message": _("Subscription registered successfully."),
                        "last_check_date": fields.Datetime.now(),
                        "remote_payload": json.dumps(response_payload, indent=2, default=str),
                    }
                )
                log_status = "success"
                message = _("Subscription registered successfully.")
            elif response is not None and response.status_code == 409:
                subscription.write(
                    {
                        "health_status": "duplicate",
                        "health_message": _("Workable reports that this subscription already exists."),
                        "last_check_date": fields.Datetime.now(),
                        "remote_payload": json.dumps(response_payload, indent=2, default=str),
                    }
                )
                log_status = "warning"
                message = subscription.health_message
            else:
                message = (
                    _("Workable returned HTTP %s while registering the subscription.") % status_code
                    if response
                    else response_payload.get("error", _("Connection failed."))
                )
                subscription.write(
                    {
                        "health_status": "api_error",
                        "health_message": message,
                        "last_check_date": fields.Datetime.now(),
                        "remote_payload": json.dumps(response_payload, indent=2, default=str),
                    }
                )
                log_status = "error"
            subscription.account_id._create_log(
                "register",
                log_status,
                message,
                http_status=status_code,
                response_time_ms=elapsed_ms,
                response_payload=response_payload,
                subscription=subscription,
            )
        return True

    def action_unregister(self):
        for subscription in self:
            if not subscription.workable_subscription_id:
                raise UserError(_("This record has no Workable subscription ID."))
            response, payload, elapsed_ms = subscription.account_id._api_request(
                "DELETE", f"subscriptions/{subscription.workable_subscription_id}"
            )
            status_code = response.status_code if response else 0
            if response is not None and response.status_code in (200, 204, 404):
                message = _("Subscription removed from Workable.")
                subscription.write(
                    {
                        "workable_subscription_id": False,
                        "remote_target_url": False,
                        "remote_event_type": False,
                        "health_status": "missing",
                        "health_message": message,
                        "last_check_date": fields.Datetime.now(),
                    }
                )
                log_status = "success"
            else:
                message = (
                    _("Workable returned HTTP %s while removing the subscription.") % status_code
                    if response
                    else payload.get("error", _("Connection failed."))
                )
                subscription.write(
                    {
                        "health_status": "api_error",
                        "health_message": message,
                        "last_check_date": fields.Datetime.now(),
                    }
                )
                log_status = "error"
            subscription.account_id._create_log(
                "unregister",
                log_status,
                message,
                http_status=status_code,
                response_time_ms=elapsed_ms,
                response_payload=payload,
                subscription=subscription,
            )
        return True

    def action_reregister(self):
        for subscription in self:
            if subscription.workable_subscription_id:
                subscription.action_unregister()
            subscription.action_register()
        return True

    def action_check(self):
        accounts = self.mapped("account_id")
        accounts.action_check_subscriptions()
        return True

    def _remote_value(self, item, *keys):
        for key in keys:
            value = item.get(key)
            if value not in (None, ""):
                return value
        return False

    def _apply_remote_state(self, remote_items):
        now = fields.Datetime.now()
        for subscription in self:
            matches = []
            for item in remote_items:
                if not isinstance(item, dict):
                    continue
                event = subscription._remote_value(item, "event", "event_type", "type")
                target = subscription._remote_value(item, "target", "target_url", "url")
                remote_id = subscription._remote_value(item, "id", "subscription_id")
                if subscription.workable_subscription_id and str(remote_id) == str(subscription.workable_subscription_id):
                    matches.append(item)
                elif event == subscription.event_type and target == subscription.target_url:
                    matches.append(item)

            values = {"last_check_date": now}
            if not matches:
                values.update(
                    {
                        "health_status": "missing",
                        "health_message": _("No matching active subscription was found in Workable."),
                        "remote_target_url": False,
                        "remote_event_type": False,
                    }
                )
                if subscription.auto_register:
                    subscription.write(values)
                    subscription.action_register()
                    continue
            elif len(matches) > 1:
                values.update(
                    {
                        "health_status": "duplicate",
                        "health_message": _("Multiple matching subscriptions were found in Workable."),
                    }
                )
            else:
                item = matches[0]
                remote_id = subscription._remote_value(item, "id", "subscription_id")
                remote_event = subscription._remote_value(item, "event", "event_type", "type")
                remote_target = subscription._remote_value(item, "target", "target_url", "url")
                values.update(
                    {
                        "workable_subscription_id": str(remote_id or subscription.workable_subscription_id or ""),
                        "remote_event_type": remote_event,
                        "remote_target_url": remote_target,
                        "remote_payload": json.dumps(item, indent=2, default=str),
                    }
                )
                if remote_event and remote_event != subscription.event_type:
                    values.update(
                        {
                            "health_status": "event_mismatch",
                            "health_message": _("The Workable event does not match the configured event."),
                        }
                    )
                elif remote_target and remote_target.rstrip("/") != (subscription.target_url or "").rstrip("/"):
                    values.update(
                        {
                            "health_status": "url_mismatch",
                            "health_message": _("The Workable target URL does not match the configured target."),
                        }
                    )
                elif subscription._is_webhook_stale(now):
                    values.update(
                        {
                            "health_status": "webhook_stale",
                            "health_message": _("The subscription exists, but no recent webhook has been received."),
                        }
                    )
                else:
                    values.update(
                        {
                            "health_status": "healthy",
                            "health_message": _("Subscription exists and matches the Odoo configuration."),
                        }
                    )
            subscription.write(values)

    def _is_webhook_stale(self, now):
        self.ensure_one()
        hours = self.account_id.stale_webhook_hours
        if not hours or not self.last_webhook_received:
            return False
        return self.last_webhook_received < now - timedelta(hours=hours)
