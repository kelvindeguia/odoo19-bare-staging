# -*- coding: utf-8 -*-

import hashlib
import json
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class WorkableWebhookEvent(models.Model):
    _name = "workable.webhook.event"
    _description = "Workable Webhook Event"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "received_at desc, id desc"

    name = fields.Char(string="Event Name", required=True, default="Workable Webhook")
    event_type = fields.Char(string="Event Type", index=True)
    workable_object_type = fields.Selection([
        ("candidate", "Candidate"),
        ("requisition", "Hiring Plan / Requisition"),
        ("job", "Job"),
        ("department", "Department"),
        ("unknown", "Unknown"),
    ], string="Object Type", default="unknown", index=True)
    external_id = fields.Char(string="External ID", index=True)
    candidate_stage = fields.Char(string="Candidate Target Stage", index=True)
    candidate_previous_stage = fields.Char(string="Candidate Previous Stage")
    candidate_is_hired_move = fields.Boolean(string="Candidate Moved to Hired", index=True)
    payload_json = fields.Json(string="Payload JSON")
    payload_hash = fields.Char(string="Payload Hash", index=True)
    state = fields.Selection([
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("done", "Done"),
        ("failed", "Failed"),
        ("ignored", "Ignored"),
    ], string="State", default="pending", index=True, tracking=True)
    received_at = fields.Datetime(string="Received At", default=fields.Datetime.now, index=True)
    processed_at = fields.Datetime(string="Processed At", readonly=True)
    retry_count = fields.Integer(string="Retry Count", default=0)
    error_message = fields.Text(string="Error Message")
    source_ip = fields.Char(string="Source IP")
    header_json = fields.Json(string="Headers")

    _sql_constraints = [
        ("payload_hash_uniq", "unique(payload_hash)", "This webhook payload was already received."),
    ]

    @api.model
    def _payload_hash(self, payload):
        payload_text = json.dumps(payload or {}, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(payload_text.encode("utf-8")).hexdigest()

    @api.model
    def _detect_event_type(self, payload):
        if not isinstance(payload, dict):
            return "unknown"
        event = payload.get("event") or payload.get("event_type") or payload.get("action") or payload.get("type") or "unknown"
        if isinstance(event, dict):
            return event.get("name") or event.get("type") or event.get("event") or "unknown"
        return event

    @api.model
    def _deep_find_key(self, value, keys):
        if isinstance(value, dict):
            for key in keys:
                if value.get(key):
                    return value.get(key)
            for nested in value.values():
                found = self._deep_find_key(nested, keys)
                if found:
                    return found
        elif isinstance(value, list):
            for nested in value:
                found = self._deep_find_key(nested, keys)
                if found:
                    return found
        return False

    @api.model
    def _detect_object_type(self, payload):
        event_text = json.dumps(payload or {}, ensure_ascii=False).lower()
        if "candidate" in event_text:
            return "candidate"
        if "requisition" in event_text or "hiring" in event_text:
            return "requisition"
        if "job" in event_text:
            return "job"
        if "department" in event_text:
            return "department"
        return "unknown"

    @api.model
    def _normalize_text(self, value):
        if isinstance(value, dict):
            value = value.get("slug") or value.get("name") or value.get("label") or value.get("title") or ""
        return str(value or "").strip()

    @api.model
    def _extract_candidate_id(self, payload):
        if not isinstance(payload, dict):
            return False

        candidate = payload.get("candidate")
        data = payload.get("data")
        if not isinstance(candidate, dict) and isinstance(data, dict):
            candidate = data.get("candidate")
        if isinstance(candidate, dict):
            candidate_id = (
                candidate.get("id")
                or candidate.get("candidate_id")
                or candidate.get("shortcode")
                or candidate.get("short_code")
                or candidate.get("uuid")
            )
            if candidate_id:
                return candidate_id

        return self._deep_find_key(payload, [
            "candidate_id",
            "candidateId",
            "candidate_uuid",
            "candidate_shortcode",
            "shortcode",
            "short_code",
            "id",
            "uuid",
        ])

    @api.model
    def _extract_stage_value(self, payload):
        if not isinstance(payload, dict):
            return ""

        candidates = []

        for key in ("target_stage", "to_stage", "new_stage", "stage", "stage_slug", "target_stage_slug"):
            if payload.get(key):
                candidates.append(payload.get(key))

        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("target_stage", "to_stage", "new_stage", "stage", "stage_slug", "target_stage_slug"):
                if data.get(key):
                    candidates.append(data.get(key))

        candidate = payload.get("candidate")
        if not isinstance(candidate, dict) and isinstance(data, dict):
            candidate = data.get("candidate")
        if isinstance(candidate, dict):
            for key in ("target_stage", "to_stage", "new_stage", "stage", "stage_slug", "target_stage_slug"):
                if candidate.get(key):
                    candidates.append(candidate.get(key))

        event = payload.get("event") or payload.get("event_type") or {}
        if isinstance(event, dict):
            for key in ("target_stage", "to_stage", "new_stage", "stage", "stage_slug", "target_stage_slug"):
                if event.get(key):
                    candidates.append(event.get(key))

        for candidate_stage in candidates:
            stage = self._normalize_text(candidate_stage)
            if stage:
                return stage
        return ""

    @api.model
    def _extract_previous_stage_value(self, payload):
        if not isinstance(payload, dict):
            return ""
        for key in ("previous_stage", "from_stage", "old_stage", "source_stage"):
            value = self._deep_find_key(payload, [key])
            if value:
                return self._normalize_text(value)
        return ""

    @api.model
    def _is_hired_stage(self, stage):
        return self._normalize_text(stage).lower() == "hired"

    @api.model
    def create_from_payload(self, payload, headers=None, source_ip=False):
        headers = headers or {}
        payload_hash = self._payload_hash(payload)
        existing = self.sudo().search([("payload_hash", "=", payload_hash)], limit=1)
        if existing:
            return existing

        object_type = self._detect_object_type(payload)
        event_type = self._detect_event_type(payload)

        if object_type == "candidate":
            external_id = self._extract_candidate_id(payload)
        else:
            external_id = self._deep_find_key(payload, [
                "requisition_id", "job_id", "department_id", "id", "shortcode", "code"
            ])

        candidate_stage = self._extract_stage_value(payload) if object_type == "candidate" else ""
        candidate_previous_stage = self._extract_previous_stage_value(payload) if object_type == "candidate" else ""
        candidate_is_hired_move = (
            object_type == "candidate"
            and event_type == "candidate_moved"
            and self._is_hired_stage(candidate_stage)
        )

        return self.sudo().create({
            "name": "%s - %s" % (event_type or "Workable Webhook", external_id or "No ID"),
            "event_type": event_type,
            "workable_object_type": object_type,
            "external_id": str(external_id or ""),
            "candidate_stage": candidate_stage,
            "candidate_previous_stage": candidate_previous_stage,
            "candidate_is_hired_move": candidate_is_hired_move,
            "payload_json": payload,
            "payload_hash": payload_hash,
            "source_ip": source_ip or "",
            "header_json": headers,
        })

    def action_process_event(self):
        for event in self:
            event._process_event()
        return True

    def _process_event(self):
        self.ensure_one()
        if self.state == "done":
            return True

        self.sudo().write({"state": "processing", "retry_count": self.retry_count + 1, "error_message": False})
        try:
            if self.workable_object_type == "candidate":
                candidate_id = self._extract_candidate_id(self.payload_json) or self.external_id
                if not candidate_id:
                    self.sudo().write({
                        "state": "ignored",
                        "processed_at": fields.Datetime.now(),
                        "error_message": "Candidate webhook did not include a candidate ID.",
                    })
                    return True

                candidate_model = self.env["workable.candidate"].sudo().with_context(skip_workable_outbound_sync=True)

                if self.event_type == "candidate_moved":
                    candidate_model._process_candidate_moved_webhook(
                        candidate_id,
                        target_stage=self.candidate_stage,
                        webhook_event=self,
                    )
                else:
                    payload = candidate_model._fetch_candidate_detail(candidate_id)
                    candidate_model._upsert_candidate_payload(
                        payload,
                        source="webhook",
                        webhook_event=self,
                    )

            elif self.workable_object_type == "requisition":
                # Webhook payloads are often notifications only. Requisition/hiring plan data remains API-driven.
                # Keep this event for traceability and let reconciliation API sync update the actual record.
                self.sudo().write({
                    "state": "ignored",
                    "processed_at": fields.Datetime.now(),
                    "error_message": "Requisition webhook stored. Hiring Plans are synced by API reconciliation.",
                })
                return True

            else:
                self.sudo().write({
                    "state": "ignored",
                    "processed_at": fields.Datetime.now(),
                    "error_message": "Webhook object type is not currently actionable.",
                })
                return True

            self.sudo().write({"state": "done", "processed_at": fields.Datetime.now()})
            return True
        except Exception as exc:
            _logger.exception("Failed processing Workable webhook event %s", self.id)
            self.sudo().write({"state": "failed", "error_message": str(exc)})
            return False

    @api.model
    def cron_process_pending_events(self, limit=50):
        events = self.sudo().search([
            ("state", "in", ["pending", "failed"]),
            ("retry_count", "<", 5),
        ], order="received_at asc", limit=limit)
        for event in events:
            event._process_event()
        return True
