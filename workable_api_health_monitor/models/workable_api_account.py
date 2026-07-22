import hashlib
import hmac
import json
import logging
import secrets
import time
from urllib.parse import urljoin

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class WorkableApiAccount(models.Model):
    _name = "workable.api.account"
    _description = "Workable API Account"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    environment = fields.Selection(
        [
            ("production", "Production"),
            ("staging", "Staging"),
            ("development", "Development"),
            ("other", "Other"),
        ],
        required=True,
        default="production",
        tracking=True,
    )
    purpose = fields.Selection(
        [
            ("candidate", "Candidate Integration"),
            ("employee", "Employee Integration"),
            ("webhook", "Webhook Subscription"),
            ("reporting", "Reporting"),
            ("general", "General API Access"),
        ],
        required=True,
        default="general",
        tracking=True,
    )
    subdomain = fields.Char(
        required=True,
        tracking=True,
        help="Only the Workable account subdomain, without .workable.com.",
    )
    api_token = fields.Char(
        required=True,
        groups="workable_api_health_monitor.group_workable_health_admin",
        copy=False,
    )
    webhook_secret = fields.Char(
        groups="workable_api_health_monitor.group_workable_health_admin",
        copy=False,
        help="Optional. When empty, the API token is used as the HMAC signing key.",
    )
    webhook_key = fields.Char(
        required=True,
        default=lambda self: secrets.token_urlsafe(24),
        copy=False,
        index=True,
        readonly=True,
    )
    webhook_url = fields.Char(compute="_compute_webhook_url")
    api_base_url = fields.Char(compute="_compute_api_base_url")
    auth_scheme = fields.Selection(
        [("bearer", "Bearer Token"), ("raw", "Raw Authorization Value")],
        required=True,
        default="bearer",
        help="Bearer Token sends 'Authorization: Bearer <token>'. Raw sends the token exactly as the Authorization value.",
    )
    request_timeout = fields.Integer(default=30, required=True)
    verify_ssl = fields.Boolean(default=True)

    health_check_enabled = fields.Boolean(default=True, tracking=True)
    alert_enabled = fields.Boolean(default=True)
    failure_threshold = fields.Integer(default=3, required=True)
    stale_webhook_hours = fields.Integer(
        default=168,
        required=True,
        help="A subscription becomes stale after this many hours without a webhook. Set 0 to disable stale-webhook evaluation.",
    )
    alert_user_ids = fields.Many2many(
        "res.users",
        "workable_account_alert_user_rel",
        "account_id",
        "user_id",
        string="Alert Recipients",
    )

    connection_status = fields.Selection(
        [
            ("not_checked", "Not Checked"),
            ("healthy", "Healthy"),
            ("warning", "Warning"),
            ("unhealthy", "Unhealthy"),
            ("auth_error", "Authentication Error"),
            ("rate_limited", "Rate Limited"),
            ("connection_error", "Connection Error"),
        ],
        required=True,
        default="not_checked",
        readonly=True,
        tracking=True,
    )
    connection_message = fields.Text(readonly=True)
    last_check_date = fields.Datetime(readonly=True)
    last_success_date = fields.Datetime(readonly=True)
    last_webhook_at = fields.Datetime(readonly=True)
    last_invalid_webhook_at = fields.Datetime(readonly=True)
    consecutive_failures = fields.Integer(default=0, readonly=True)
    valid_webhook_count = fields.Integer(default=0, readonly=True)
    invalid_webhook_count = fields.Integer(default=0, readonly=True)
    last_response_time_ms = fields.Integer(readonly=True)

    subscription_ids = fields.One2many(
        "workable.api.subscription", "account_id", string="Subscriptions"
    )
    subscription_count = fields.Integer(compute="_compute_counts")
    healthy_subscription_count = fields.Integer(compute="_compute_counts")
    log_count = fields.Integer(compute="_compute_counts")
    webhook_event_count = fields.Integer(compute="_compute_counts")

    @api.constrains("subdomain")
    def _check_subdomain(self):
        for record in self:
            value = (record.subdomain or "").strip().lower()
            if not value or "." in value or "/" in value or " " in value:
                raise ValidationError(
                    _("Enter only the Workable subdomain, for example 'mycompany'.")
                )

    @api.constrains("request_timeout", "failure_threshold", "stale_webhook_hours")
    def _check_positive_settings(self):
        for record in self:
            if record.request_timeout <= 0:
                raise ValidationError(_("Request timeout must be greater than zero."))
            if record.failure_threshold <= 0:
                raise ValidationError(_("Failure threshold must be greater than zero."))
            if record.stale_webhook_hours < 0:
                raise ValidationError(_("Stale webhook hours cannot be negative."))

    @api.depends("subdomain")
    def _compute_api_base_url(self):
        for record in self:
            subdomain = (record.subdomain or "").strip().lower()
            record.api_base_url = (
                f"https://{subdomain}.workable.com/spi/v3/" if subdomain else False
            )

    @api.depends("webhook_key")
    def _compute_webhook_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for record in self:
            record.webhook_url = (
                f"{base_url.rstrip('/')}/workable/health/webhook/{record.webhook_key}"
                if base_url and record.webhook_key
                else False
            )

    def _compute_counts(self):
        Subscription = self.env["workable.api.subscription"]
        Log = self.env["workable.health.log"]
        Event = self.env["workable.webhook.event"]
        for record in self:
            record.subscription_count = Subscription.search_count(
                [("account_id", "=", record.id)]
            )
            record.healthy_subscription_count = Subscription.search_count(
                [("account_id", "=", record.id), ("health_status", "=", "healthy")]
            )
            record.log_count = Log.search_count([("account_id", "=", record.id)])
            record.webhook_event_count = Event.search_count(
                [("account_id", "=", record.id)]
            )

    def _authorization_value(self):
        self.ensure_one()
        token = self.api_token or ""
        return f"Bearer {token}" if self.auth_scheme == "bearer" else token

    def _request_headers(self):
        self.ensure_one()
        return {
            "Authorization": self._authorization_value(),
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Odoo-19-Workable-Health-Monitor/1.0",
        }

    def _api_request(self, method, path, payload=None):
        self.ensure_one()
        if not self.api_token:
            raise UserError(_("An API token is required."))
        url = urljoin(self.api_base_url, path.lstrip("/"))
        started = time.monotonic()
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._request_headers(),
                json=payload,
                timeout=self.request_timeout,
                verify=self.verify_ssl,
            )
            elapsed_ms = int((time.monotonic() - started) * 1000)
            try:
                response_payload = response.json() if response.content else {}
            except ValueError:
                response_payload = {"raw": response.text}
            return response, response_payload, elapsed_ms
        except requests.RequestException as exc:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return None, {"error": str(exc)}, elapsed_ms

    def _create_log(
        self,
        check_type,
        status,
        message,
        http_status=0,
        response_time_ms=0,
        response_payload=None,
        subscription=None,
    ):
        self.ensure_one()
        return self.env["workable.health.log"].sudo().create(
            {
                "account_id": self.id,
                "subscription_id": subscription.id if subscription else False,
                "check_type": check_type,
                "status": status,
                "http_status": http_status or 0,
                "response_time_ms": response_time_ms or 0,
                "message": message,
                "response_payload": json.dumps(
                    response_payload or {}, indent=2, default=str
                ),
            }
        )

    def _status_from_http(self, status_code):
        if status_code in (401, 403):
            return "auth_error"
        if status_code == 429:
            return "rate_limited"
        if status_code >= 500:
            return "connection_error"
        return "unhealthy"

    def _update_account_health(self, status, message, elapsed_ms=0):
        self.ensure_one()
        previous_status = self.connection_status
        is_success = status in ("healthy", "warning")
        failures = 0 if is_success else self.consecutive_failures + 1
        values = {
            "connection_status": status,
            "connection_message": message,
            "last_check_date": fields.Datetime.now(),
            "last_response_time_ms": elapsed_ms,
            "consecutive_failures": failures,
        }
        if is_success:
            values["last_success_date"] = fields.Datetime.now()
        self.write(values)
        self._notify_health_transition(previous_status, status, message, failures)

    def _notify_health_transition(self, previous_status, new_status, message, failures):
        self.ensure_one()
        if not self.alert_enabled or not self.alert_user_ids:
            return
        should_alert = (
            new_status not in ("healthy", "warning")
            and failures >= self.failure_threshold
            and previous_status != new_status
        )
        recovered = (
            new_status == "healthy"
            and previous_status not in ("healthy", "not_checked")
        )
        if not (should_alert or recovered):
            return
        subject = (
            _("Workable API recovered: %s") % self.display_name
            if recovered
            else _("Workable API health alert: %s") % self.display_name
        )
        body = "<p><strong>%s</strong></p><p>%s</p>" % (subject, message or "")
        partner_ids = self.alert_user_ids.mapped("partner_id").ids
        self.message_post(
            subject=subject,
            body=body,
            partner_ids=partner_ids,
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )

    def action_test_connection(self):
        for account in self:
            response, payload, elapsed_ms = account._api_request("GET", "subscriptions")
            if response is None:
                message = payload.get("error", _("Connection failed."))
                account._create_log(
                    "connection", "error", message, response_time_ms=elapsed_ms,
                    response_payload=payload,
                )
                account._update_account_health("connection_error", message, elapsed_ms)
                continue
            if response.status_code == 200:
                message = _("Connection successful. Workable returned the subscription list.")
                account._create_log(
                    "connection", "success", message,
                    http_status=response.status_code,
                    response_time_ms=elapsed_ms,
                    response_payload=payload,
                )
                account._update_account_health("healthy", message, elapsed_ms)
            else:
                status = account._status_from_http(response.status_code)
                message = _("Workable returned HTTP %s.") % response.status_code
                account._create_log(
                    "connection", "error", message,
                    http_status=response.status_code,
                    response_time_ms=elapsed_ms,
                    response_payload=payload,
                )
                account._update_account_health(status, message, elapsed_ms)
        return True

    def _extract_remote_subscriptions(self, payload):
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []
        for key in ("subscriptions", "data", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        if payload.get("id"):
            return [payload]
        return []

    def action_check_subscriptions(self):
        for account in self:
            response, payload, elapsed_ms = account._api_request("GET", "subscriptions")
            if response is None or response.status_code != 200:
                status_code = response.status_code if response else 0
                status = (
                    account._status_from_http(status_code)
                    if response
                    else "connection_error"
                )
                message = (
                    _("Unable to retrieve Workable subscriptions: HTTP %s.") % status_code
                    if response
                    else payload.get("error", _("Connection failed."))
                )
                account.subscription_ids.filtered("active").write(
                    {
                        "health_status": "api_error",
                        "health_message": message,
                        "last_check_date": fields.Datetime.now(),
                    }
                )
                account._create_log(
                    "subscriptions", "error", message,
                    http_status=status_code,
                    response_time_ms=elapsed_ms,
                    response_payload=payload,
                )
                account._update_account_health(status, message, elapsed_ms)
                continue

            remote_items = account._extract_remote_subscriptions(payload)
            account.subscription_ids.filtered("active")._apply_remote_state(remote_items)
            unhealthy = account.subscription_ids.filtered(
                lambda item: item.active and item.health_status != "healthy"
            )
            if unhealthy:
                status = "warning"
                message = _("API is reachable, but %s subscription(s) require attention.") % len(unhealthy)
                log_status = "warning"
            else:
                status = "healthy"
                message = _("API is reachable and all configured subscriptions are healthy.")
                log_status = "success"
            account._create_log(
                "subscriptions", log_status, message,
                http_status=response.status_code,
                response_time_ms=elapsed_ms,
                response_payload=payload,
            )
            account._update_account_health(status, message, elapsed_ms)
        return True

    def action_run_full_health_check(self):
        return self.action_check_subscriptions()

    def action_register_all_subscriptions(self):
        for account in self:
            account.subscription_ids.filtered(
                lambda item: item.active and not item.workable_subscription_id
            ).action_register()
        return self.action_check_subscriptions()

    def action_reset_failure_counter(self):
        self.write({"consecutive_failures": 0})
        return True

    def action_regenerate_webhook_key(self):
        self.ensure_one()
        self.webhook_key = secrets.token_urlsafe(24)
        return True

    def _extract_event_type(self, payload):
        if not isinstance(payload, dict):
            return ""
        return (
            payload.get("event")
            or payload.get("event_type")
            or payload.get("type")
            or (payload.get("subscription") or {}).get("event")
            or ""
        )

    def _validate_webhook_signature(self, raw_body, received_signature):
        self.ensure_one()
        if not received_signature:
            return False
        signing_key = self.webhook_secret or self.api_token or ""
        expected = hmac.new(
            signing_key.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        candidate = received_signature
        if candidate.lower().startswith("sha256="):
            candidate = candidate.split("=", 1)[1]
        return hmac.compare_digest(expected.lower(), candidate.lower())

    def action_open_subscriptions(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "workable_api_health_monitor.action_workable_api_subscription"
        )
        action["domain"] = [("account_id", "=", self.id)]
        action["context"] = {"default_account_id": self.id}
        return action

    def action_open_logs(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "workable_api_health_monitor.action_workable_health_log"
        )
        action["domain"] = [("account_id", "=", self.id)]
        return action

    def action_open_webhook_events(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "workable_api_health_monitor.action_workable_webhook_event"
        )
        action["domain"] = [("account_id", "=", self.id)]
        return action

    @api.model
    def _cron_check_all_accounts(self):
        accounts = self.search(
            [("active", "=", True), ("health_check_enabled", "=", True)]
        )
        for account in accounts:
            try:
                with self.env.cr.savepoint():
                    account.action_run_full_health_check()
            except Exception as exc:  # cron must continue with other accounts
                _logger.exception(
                    "Unexpected Workable health-check failure for %s",
                    account.display_name,
                )
                account._create_log(
                    "full", "error", str(exc), response_payload={"error": str(exc)}
                )
                account._update_account_health("connection_error", str(exc))
        return True
