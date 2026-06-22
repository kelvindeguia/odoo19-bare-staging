# -*- coding: utf-8 -*-

import json
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class WorkableCandidate(models.Model):
    _name = "workable.candidate"
    _description = "Workable Candidate"
    _inherit = ["mail.thread", "mail.activity.mixin", "workable.api.mixin"]
    _order = "workable_updated_at desc, id desc"
    _rec_name = "display_name"

    workable_candidate_id = fields.Char(
        string="Workable Candidate ID",
        required=True,
        index=True,
        copy=False,
        tracking=True,
    )
    display_name = fields.Char(
        string="Candidate",
        compute="_compute_display_name",
        store=True,
    )
    name = fields.Char(string="Full Name", tracking=True)
    firstname = fields.Char(string="First Name")
    lastname = fields.Char(string="Last Name")
    email = fields.Char(string="Email", tracking=True)
    phone = fields.Char(string="Phone")
    headline = fields.Char(string="Headline")
    summary = fields.Text(string="Summary")
    address = fields.Char(string="Address")
    stage = fields.Char(string="Stage", tracking=True)
    status = fields.Char(string="Status", tracking=True)
    is_hired = fields.Boolean(string="Hired", tracking=True, index=True)
    hired_at = fields.Datetime(string="Hired At", tracking=True)
    last_webhook_event_id = fields.Many2one(
        "workable.webhook.event",
        string="Last Webhook Event",
        readonly=True,
        ondelete="set null",
    )
    sourced = fields.Boolean(string="Sourced")
    job_shortcode = fields.Char(string="Job Shortcode", index=True)
    job_title = fields.Char(string="Job Title")
    profile_url = fields.Char(string="Workable Profile URL")
    workable_created_at = fields.Datetime(string="Workable Created At")
    workable_updated_at = fields.Datetime(string="Workable Updated At", index=True)
    last_synced_at = fields.Datetime(string="Last Synced At", readonly=True)
    last_sync_source = fields.Selection(
        [
            ("api", "API Sync"),
            ("webhook", "Webhook"),
            ("manual", "Manual"),
            ("odoo", "Odoo"),
        ],
        string="Last Sync Source",
        default="api",
        readonly=True,
    )
    raw_json = fields.Json(string="Raw Candidate JSON")
    answer_ids = fields.One2many(
        "workable.candidate.answer",
        "candidate_id",
        string="Custom Answers",
    )

    _sql_constraints = [
        (
            "workable_candidate_id_uniq",
            "unique(workable_candidate_id)",
            "Workable Candidate ID must be unique.",
        ),
    ]

    @api.depends("name", "firstname", "lastname", "email")
    def _compute_display_name(self):
        for rec in self:
            parts = [part for part in [rec.firstname, rec.lastname] if part]
            rec.display_name = (
                rec.name
                or " ".join(parts)
                or rec.email
                or rec.workable_candidate_id
                or _("Candidate")
            )

    def _to_datetime(self, value):
        if not value:
            return False

        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d %H:%M:%S")

        if isinstance(value, str):
            value = value.strip()
            if not value:
                return False

            value = value.replace("T", " ").replace("Z", "")

            if "+" in value:
                value = value.split("+", 1)[0]

            if "." in value:
                value = value.split(".", 1)[0]

            return value[:19]

        return False

    def _extract_custom_value(self, value):
        if value in (None, False, ""):
            return False

        if not isinstance(value, dict):
            return value

        for key in (
            "body",
            "number",
            "checked",
            "date",
            "datetime",
            "email",
            "phone",
            "url",
        ):
            if key in value:
                return value.get(key)

        if "choices" in value:
            choices = value.get("choices") or []
            return ", ".join(
                str(choice)
                for choice in choices
                if choice not in (None, "")
            )

        if "file" in value:
            file_value = value.get("file") or {}
            return (
                file_value.get("url")
                or file_value.get("preview_url")
                or file_value.get("name")
            )

        if "files" in value:
            result = []
            for item in value.get("files") or []:
                if isinstance(item, dict):
                    result.append(
                        item.get("url")
                        or item.get("preview_url")
                        or item.get("name")
                        or str(item)
                    )
                else:
                    result.append(str(item))
            return ", ".join(result)

        return json.dumps(value, ensure_ascii=False)

    def _unwrap_candidate_payload(self, payload):
        """
        Workable candidate endpoints can return either:

            {"candidate": {...}}

        or:

            {...candidate fields directly...}

        This method normalizes both formats.
        """
        if not isinstance(payload, dict):
            return {}

        for key in ("candidate", "data"):
            value = payload.get(key)
            if isinstance(value, dict):
                return value

        return payload

    def _get_candidate_external_id(self, candidate):
        """
        Return the stable Workable candidate identifier from list/detail/webhook payloads.

        Some Workable responses use `id`, while some list/event payloads may expose
        `shortcode`, `candidate_id`, or similar fields.
        """
        candidate = self._unwrap_candidate_payload(candidate)

        if not isinstance(candidate, dict):
            return False

        return (
            candidate.get("id")
            or candidate.get("candidate_id")
            or candidate.get("shortcode")
            or candidate.get("short_code")
            or candidate.get("uuid")
        )

    def _map_candidate(self, candidate):
        candidate = self._unwrap_candidate_payload(candidate)
        candidate_id = self._get_candidate_external_id(candidate)

        job = candidate.get("job") or {}
        stage = candidate.get("stage") or {}

        if isinstance(stage, dict):
            stage_name = stage.get("name") or stage.get("slug") or ""
        else:
            stage_name = stage or ""

        status_name = candidate.get("status") or candidate.get("state") or ""
        hired_flag = str(stage_name or status_name or "").strip().lower() == "hired"

        return {
            "workable_candidate_id": str(candidate_id or ""),
            "name": candidate.get("name") or candidate.get("full_name") or "",
            "firstname": candidate.get("firstname") or candidate.get("first_name") or "",
            "lastname": candidate.get("lastname") or candidate.get("last_name") or "",
            "email": candidate.get("email") or candidate.get("mail") or "",
            "phone": candidate.get("phone") or candidate.get("phone_number") or "",
            "headline": candidate.get("headline") or "",
            "summary": candidate.get("summary") or candidate.get("cover_letter") or "",
            "address": candidate.get("address") or "",
            "stage": stage_name,
            "status": status_name,
            "is_hired": hired_flag,
            "sourced": bool(candidate.get("sourced"))
            if candidate.get("sourced") is not None
            else False,
            "job_shortcode": job.get("shortcode") if isinstance(job, dict) else "",
            "job_title": job.get("title") if isinstance(job, dict) else "",
            "profile_url": candidate.get("profile_url") or candidate.get("url") or "",
            "workable_created_at": self._to_datetime(candidate.get("created_at")),
            "workable_updated_at": self._to_datetime(candidate.get("updated_at")),
            "last_synced_at": fields.Datetime.now(),
            "raw_json": candidate,
        }

    def _sync_candidate_answers(self, candidate_rec, candidate_payload):
        candidate_payload = self._unwrap_candidate_payload(candidate_payload)
        answers = candidate_payload.get("answers") or []

        existing_by_key = {
            (answer.question or answer.question_key or "").strip().lower(): answer
            for answer in candidate_rec.answer_ids
        }

        for item in answers:
            if not isinstance(item, dict):
                continue

            question = item.get("question") or {}
            answer = item.get("answer") or item.get("value") or {}

            if isinstance(question, dict):
                question_text = question.get("body") or ""
                question_key = question.get("key") or question.get("id") or question_text
            else:
                question_text = str(question or "")
                question_key = question_text

            parsed_value = self._extract_custom_value(answer)
            key = (question_text or question_key or "").strip().lower()

            if not key:
                continue

            vals = {
                "candidate_id": candidate_rec.id,
                "question": question_text or question_key,
                "question_key": str(question_key or ""),
                "answer_text": str(parsed_value)
                if parsed_value not in (None, False)
                else "",
                "answer_json": item,
            }

            if isinstance(parsed_value, bool):
                vals["answer_boolean"] = parsed_value
            elif isinstance(parsed_value, (int, float)):
                vals["answer_number"] = float(parsed_value)

            existing = existing_by_key.get(key)

            if existing:
                existing.write(vals)
            else:
                self.env["workable.candidate.answer"].sudo().create(vals)

    def _upsert_candidate_payload(self, candidate_payload, source="api", webhook_event=False, force_stage=False, force_hired=False):
        candidate_payload = self._unwrap_candidate_payload(candidate_payload)
        candidate_id = self._get_candidate_external_id(candidate_payload)

        if not candidate_id:
            _logger.warning(
                "Skipping Workable candidate payload because no candidate ID was found. Payload keys: %s",
                list(candidate_payload.keys())
                if isinstance(candidate_payload, dict)
                else type(candidate_payload),
            )
            return False

        vals = self._map_candidate(candidate_payload)
        vals["last_sync_source"] = source

        if force_stage:
            vals["stage"] = force_stage

        if force_hired:
            vals["is_hired"] = True
            if not vals.get("hired_at"):
                vals["hired_at"] = fields.Datetime.now()

        if webhook_event:
            vals["last_webhook_event_id"] = webhook_event.id

        existing = self.sudo().search(
            [("workable_candidate_id", "=", str(candidate_id))],
            limit=1,
        )

        context = dict(
            self.env.context,
            skip_workable_outbound_sync=True,
        )

        if existing:
            existing.with_context(context).sudo().write(vals)
            candidate_rec = existing
        else:
            candidate_rec = self.with_context(context).sudo().create(vals)

        self._sync_candidate_answers(candidate_rec, candidate_payload)
        return candidate_rec

    def _fetch_candidate_detail(self, candidate_id):
        data = self._workable_request("GET", "/candidates/%s" % candidate_id)
        return self._unwrap_candidate_payload(data)

    def _fetch_candidates_from_workable(self, progress=False, limit=100, max_pages=10000):
        """
        Fetch candidate list records from Workable.

        Important:
        - This method fetches the candidate list endpoint only.
        - It includes paging-loop protection because a repeated paging.next value
          would otherwise keep the sync alive indefinitely.
        - Full candidate detail should be fetched only from webhook/manual detail refresh,
          not for every candidate during the main sync.
        """
        candidates = []
        path = "/candidates"
        params = {"limit": limit}
        first_call = True
        page = 1
        seen_next_paths = set()

        while path:
            if page > max_pages:
                _logger.warning(
                    "Stopping Workable candidate fetch because max_pages=%s was reached. total_fetched=%s last_path=%s",
                    max_pages,
                    len(candidates),
                    path,
                )
                break

            data = self._workable_request(
                "GET",
                path,
                params=params if first_call else None,
            )
            first_call = False

            page_candidates = data.get("candidates") or []
            candidates.extend(page_candidates)

            if progress:
                self.env["workable.sync.service"]._update_fetch_count(
                    progress,
                    "Candidates",
                    page,
                    len(page_candidates),
                    len(candidates),
                )

            next_path = (data.get("paging") or {}).get("next")

            if next_path and next_path in seen_next_paths:
                _logger.warning(
                    "Stopping Workable candidate fetch because paging.next repeated. next=%s total_fetched=%s",
                    next_path,
                    len(candidates),
                )
                break

            if next_path:
                seen_next_paths.add(next_path)

            path = next_path
            page += 1

        _logger.info("Fetched %s Workable candidate list records.", len(candidates))
        return candidates

    def _process_candidates(self, candidates, fetch_details=False, source="api", progress=False, batch_size=500):
        """
        Create/update candidates in Odoo.

        Default behavior is intentionally list-only. Fetching detail for every
        candidate is too expensive for large datasets such as 41k candidates and
        can make the sync look stuck for hours. Candidate details/custom answers
        should be updated by webhook or a targeted manual refresh.
        """
        created = 0
        updated = 0
        failed = 0

        candidate_items = candidates or []
        candidate_ids = []
        for item in candidate_items:
            candidate_id = self._get_candidate_external_id(item)
            if candidate_id:
                candidate_ids.append(str(candidate_id))

        existing_ids = set()
        for start in range(0, len(candidate_ids), 1000):
            chunk = candidate_ids[start:start + 1000]
            existing_ids.update(
                self.sudo()
                .search([("workable_candidate_id", "in", chunk)])
                .mapped("workable_candidate_id")
            )

        total = len(candidate_items)

        for index, item in enumerate(candidate_items, start=1):
            candidate_id = self._get_candidate_external_id(item)

            if not candidate_id:
                _logger.warning(
                    "Skipping Workable candidate list item because no candidate ID was found. Item keys: %s",
                    list(item.keys()) if isinstance(item, dict) else type(item),
                )
                failed += 1
                continue

            candidate_id = str(candidate_id)

            try:
                payload = (
                    self._fetch_candidate_detail(candidate_id)
                    if fetch_details
                    else item
                )

                candidate_rec = self._upsert_candidate_payload(
                    payload,
                    source=source,
                )

                if not candidate_rec:
                    failed += 1
                    continue

                if candidate_id in existing_ids:
                    updated += 1
                else:
                    created += 1
                    existing_ids.add(candidate_id)

            except Exception:
                failed += 1
                _logger.exception(
                    "Failed to process Workable candidate %s",
                    candidate_id,
                )

            if progress and (index % batch_size == 0 or index == total):
                progress.sudo().write({
                    "current_model": "Candidates",
                    "current_batch_count": index,
                    "current_total_fetched": total,
                    "message": "Processed %s / %s Candidates" % (index, total),
                })
                self.env.cr.commit()

        return created, updated, failed, []

    def _normalize_stage_value(self, stage_value):
        """Return a readable stage value from Workable payload fragments."""
        if isinstance(stage_value, dict):
            return (
                stage_value.get("slug")
                or stage_value.get("name")
                or stage_value.get("label")
                or stage_value.get("title")
                or ""
            )
        return stage_value or ""

    def _is_hired_stage_value(self, stage_value):
        stage_value = self._normalize_stage_value(stage_value)
        return str(stage_value or "").strip().lower() == "hired"

    def _process_candidate_moved_webhook(self, candidate_id, target_stage=False, webhook_event=False):
        """
        Process a Workable candidate_moved webhook.

        The webhook payload should be treated as a notification. We fetch the
        latest candidate details from Workable, update the Odoo candidate mirror,
        and explicitly mark the candidate as hired when the target stage is Hired.
        """
        if not candidate_id:
            return False

        force_stage = self._normalize_stage_value(target_stage)
        force_hired = self._is_hired_stage_value(force_stage)

        payload = self._fetch_candidate_detail(candidate_id)
        candidate_rec = self._upsert_candidate_payload(
            payload,
            source="webhook",
            webhook_event=webhook_event,
            force_stage=force_stage,
            force_hired=force_hired,
        )

        return candidate_rec

    def action_sync_candidates_from_workable(self):
        candidates = self._fetch_candidates_from_workable()
        created, updated, failed, _fields = self._process_candidates(
            candidates,
            fetch_details=False,
            source="api",
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Workable Candidates Sync"),
                "message": _(
                    "Candidates sync complete: %s created, %s updated, %s failed."
                )
                % (created, updated, failed),
                "type": "success" if not failed else "warning",
                "sticky": False,
            },
        }


class WorkableCandidateAnswer(models.Model):
    _name = "workable.candidate.answer"
    _description = "Workable Candidate Custom Answer"
    _order = "candidate_id, question"

    candidate_id = fields.Many2one(
        "workable.candidate",
        string="Candidate",
        required=True,
        ondelete="cascade",
        index=True,
    )
    question = fields.Char(string="Question", required=True)
    question_key = fields.Char(string="Question Key")
    answer_text = fields.Text(string="Answer")
    answer_number = fields.Float(string="Numeric Answer")
    answer_boolean = fields.Boolean(string="Boolean Answer")
    answer_json = fields.Json(string="Raw Answer JSON")