# -*- coding: utf-8 -*-
import requests
import logging
import time
from datetime import date, datetime

from odoo import models, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

WORKABLE_API_BASE = "https://{subdomain}.workable.com/spi/v3"


class WorkableHiringPlanSync(models.Model):
    _inherit = 'workable.hiring.plan'

    # -------------------------------
    # Credentials
    # -------------------------------
    def _get_workable_credentials(self):
        ICP = self.env['ir.config_parameter'].sudo()
        token = ICP.get_param('workable.api_token')
        subdomain = ICP.get_param('workable.subdomain')

        if not token or not subdomain:
            raise UserError(
                'Workable API Token or Subdomain is not configured. '
                'Go to Settings > General Settings > Workable Integration.'
            )

        return token.strip(), subdomain.strip()

    # -------------------------------
    # Safe Request with Retry
    # -------------------------------
    def _safe_request(self, url, headers, params=None):
        max_retries = 5
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers, params=params, timeout=30)

                # Handle rate limit
                if response.status_code == 429:
                    _logger.warning(
                        "Workable rate limit hit. Retrying in %s seconds (attempt %s/%s)",
                        retry_delay, attempt + 1, max_retries
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue

                response.raise_for_status()
                return response

            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise UserError(f"Failed to connect to Workable: {str(e)}")
                time.sleep(retry_delay)
                retry_delay *= 2

        raise UserError("Max retries exceeded due to rate limiting.")

    # -------------------------------
    # Fetch Requisitions (Optimized)
    # -------------------------------
    def _fetch_workable_requisitions(self, progress=False):
        token, subdomain = self._get_workable_credentials()

        base_url = WORKABLE_API_BASE.format(subdomain=subdomain)
        url = f"{base_url}/requisitions"

        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
        }

        # Get last sync (optional incremental support)
        ICP = self.env['ir.config_parameter'].sudo()
        last_sync = ICP.get_param('workable.last_sync')

        params = {
            'limit': 100,  # MAX allowed → fewer requests
        }

        # OPTIONAL incremental (enable if supported by API)
        # if last_sync:
        #     params['updated_after'] = last_sync

        requisitions = []
        first_call = True
        page = 1

        while url:
            _logger.info("Fetching Workable page %s", page)

            response = self._safe_request(
                url,
                headers,
                params=params if first_call else None
            )

            first_call = False

            try:
                data = response.json()
            except Exception:
                raise UserError(f"Invalid JSON response: {response.text}")

            page_reqs = data.get('requisitions', [])
            requisitions.extend(page_reqs)

            if progress:
                self.env["workable.sync.service"]._update_fetch_count(
                    progress,
                    "Hiring Plans",
                    page,
                    len(page_reqs),
                    len(requisitions)
                )

            _logger.info("Fetched %s records (total so far: %s)", len(page_reqs), len(requisitions))

            # Pagination
            url = data.get('paging', {}).get('next')

            page += 1

            # Respect rate limit
            if url:
                time.sleep(2)

        # Save last sync timestamp
        ICP.set_param('workable.last_sync', datetime.utcnow().isoformat())

        return requisitions

    def _find_department(self, department):
        if not department:
            return False

        workable_department_id = department.get('id') if isinstance(department, dict) else False
        department_name = department.get('name') if isinstance(department, dict) else department

        domain = False

        if workable_department_id:
            domain = [('department_id', '=', workable_department_id)]
        elif department_name:
            domain = [('name', '=', department_name)]

        if not domain:
            return False

        department_rec = self.env['workable.department'].search(domain, limit=1)
        return department_rec.id if department_rec else False


    def _find_job(self, job):
        if not job:
            return False

        workable_job_id = job.get('id') if isinstance(job, dict) else False
        shortcode = job.get('shortcode') if isinstance(job, dict) else False
        title = job.get('title') if isinstance(job, dict) else job

        domain = False

        if workable_job_id:
            domain = [('workable_job_id', '=', workable_job_id)]
        elif shortcode:
            domain = [('shortcode', '=', shortcode)]
        elif title:
            domain = [('title', '=', title)]

        if not domain:
            return False

        job_rec = self.env['workable.job'].search(domain, limit=1)
        return job_rec.id if job_rec else False

    # -------------------------------
    # Mapping
    # -------------------------------
    def _map_requisition(self, req):
        job = req.get('job', {})
        department = req.get('department', {})
        location = req.get('location', {})
        hiring_manager = req.get('hiring_manager', {})
        owner = req.get('owner', {})
        requester = req.get('requester', {})
        salary = req.get('salary_range', {})

        calibration_notes_url = None
        for attr in req.get('requisition_attributes', []):
            if attr.get('name') == 'Calibration Notes':
                calibration_notes_url = (attr.get('value') or {}).get('preview_url')
                break

        employment_type_map = {
            'Full-time': 'full_time',
            'Part-time': 'part_time',
            'Contract': 'contract',
            'Temporary': 'temporary',
        }

        reason_map = {
            'new_hire': 'new_hire',
            'replacement': 'replacement',
            'backfill': 'backfill',
        }

        approved_by = self._normalize_approved_by(req.get('approval_groups', []))
        status = self._normalize_requisition_status(req.get('state'))

        return {
            'requisition_id': req.get('code', ''),
            'workable_requisition_id': req.get('id', ''),
            'job_title': job.get('title', ''),
            'workable_job_id': job.get('id', ''),
            'workable_shortcode': job.get('shortcode', ''),
            'department': department.get('name', ''),
            'workable_department_id': department.get('id', ''),

            # Many2one auto-link
            'department_id': self._find_department(department),
            'job_id': self._find_job(job),

            'requisition_location': location.get('location_str', ''),
            'hiring_manager': hiring_manager.get('name', ''),
            'requisition_owner': owner.get('name', ''),
            'requestor': requester.get('name', ''),
            'plan_date': self._to_odoo_date(req.get('plan_date')),
            'target_start_date': self._to_odoo_date(req.get('start_date')),
            'employment_type': employment_type_map.get(req.get('employment_type'), 'full_time'),
            'reason': reason_map.get(req.get('reason'), 'new_hire'),
            'salary_from': salary.get('from') or 0.0,
            'salary_to': salary.get('to') or 0.0,
            'salary_currency': salary.get('currency', ''),
            'salary_frequency': salary.get('frequency', ''),
            'calibration_notes_url': calibration_notes_url,
            'approved_by': approved_by,
            'status': status,
        }

    # -------------------------------
    # Create / Update
    # -------------------------------
    def _process_requisitions(self, requisitions):
        created = 0
        updated_records = 0
        field_changes = 0
        changed_fields = []

        for req in requisitions:
            req_code = req.get('id')
            if not req_code:
                continue

            vals = self._map_requisition(req)

            existing = self.search(
                [('workable_requisition_id', '=', req_code)],
                limit=1
            )

            if existing:
                # Workable preview URLs can change every fetch.
                # Keep the originally stored URL and do not treat it as an update.
                vals.pop('calibration_notes_url', None)

                changes_count, fields_list = self._count_changes(existing, vals)

                if changes_count > 0:
                    existing.write(vals)
                    updated_records += 1
                    field_changes += changes_count
                    changed_fields.extend(fields_list)

            else:
                self.create(vals)
                created += 1

        unique_fields = sorted(list(set(changed_fields)))

        _logger.info(
            'Workable hiring plans sync: %d created, %d records updated (%d fields modified: %s)',
            created,
            updated_records,
            field_changes,
            ', '.join(unique_fields) if unique_fields else 'none'
        )

        return created, updated_records, field_changes, unique_fields

    # -------------------------------
    # Check for Changes
    # -------------------------------
    def _count_changes(self, record, new_vals):
        fields_to_check = list(new_vals.keys())
        current_vals = record.read(fields_to_check)[0]

        changes = 0
        changed_fields = []

        for field, new_value in new_vals.items():
            current_value = current_vals.get(field)

            normalized_current = self._normalize_value(current_value)
            normalized_new = self._normalize_value(new_value)

            if normalized_current != normalized_new:
                _logger.info(
                    "HIRING PLAN CHANGE DETECTED | record_id=%s | requisition=%s | field=%s | current=%r | new=%r | raw_current=%r | raw_new=%r",
                    record.id,
                    record.requisition_id,
                    field,
                    normalized_current,
                    normalized_new,
                    current_value,
                    new_value,
                )

                changes += 1
                changed_fields.append(field)

        return changes, changed_fields
    
    # -------------------------------
    # Normalize
    # -------------------------------
    def _normalize_value(self, value):
        if value in (None, '', False):
            return False

        # Many2one from read(): [id, display_name]
        if isinstance(value, list) and len(value) == 2 and isinstance(value[0], int):
            return value[0]

        # Many2one from read(): (id, display_name)
        if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], int):
            return value[0]

        # Date / Datetime object
        if hasattr(value, 'strftime'):
            return value.strftime('%Y-%m-%d')

        # List values
        if isinstance(value, list):
            cleaned_values = [
                str(item).strip()
                for item in value
                if item not in (None, '', False)
            ]
            return ', '.join(sorted(cleaned_values)) if cleaned_values else False

        # String values
        if isinstance(value, str):
            value = value.strip()

            if not value:
                return False

            # Normalize date/datetime strings
            if len(value) >= 10 and value[4:5] == '-' and value[7:8] == '-':
                return value[:10]

            # Normalize comma-separated strings
            if ',' in value:
                cleaned_values = [
                    item.strip()
                    for item in value.split(',')
                    if item.strip()
                ]
                return ', '.join(sorted(cleaned_values)) if cleaned_values else False

            return value

        if isinstance(value, float):
            return round(value, 6)

        return value
    
    def _normalize_approved_by(self, approval_groups):
        approvers = []

        for group in approval_groups or []:
            for approver in group.get('approvers', []):
                if approver.get('decision') == 'approved':
                    name = (approver.get('name') or '').strip()
                    if name:
                        approvers.append(name)

        approvers = sorted(set(approvers))

        return ', '.join(approvers) if approvers else False

    def _normalize_requisition_status(self, status):
        if not status:
            return False

        status = str(status).strip().lower().replace(' ', '_').replace('-', '_')

        allowed_statuses = {
            'open',
            'processing',
            'draft',
            'pending',
            'rejected',
            'cancelled',
            'reserved',
            'on_hold',
            'filled',
            'approved',
            'closed',
        }

        return status if status in allowed_statuses else False

    def _to_odoo_date(self, value):
        if not value:
            return False

        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d")

        if isinstance(value, str):
            value = value.strip()
            if not value:
                return False

            # Handles:
            # 2026-05-14
            # 2026-05-14T00:00:00Z
            # 2026-05-14 00:00:00
            return value[:10]

        return False

    # -------------------------------
    # Manual Sync
    # -------------------------------
    def action_sync_from_workable(self):
        try:
            requisitions = self._fetch_workable_requisitions()
            created, updated_records, field_changes, _ = self._process_requisitions(requisitions)

            return {
                    "params": {
                        "title": "Workable Sync",
                        "message": "Sync Done: %s created, %s updated (%s field changes)" % (
                            created, updated_records, field_changes,
                        ),
                        "type": "success",
                    }
                }
        except UserError as e:
            # Optional: also log
            _logger.error("Workable requisitions sync failed: %s", e)
            return {
                "params": {
                    "title": _("Workable Sync Error"),
                    "message": str(e),
                    "type": "danger",
                }
            }

    # -------------------------------
    # Cron
    # -------------------------------
    @api.model
    def cron_sync_from_workable(self):
        try:
            requisitions = self._fetch_workable_requisitions()
            created, updated_records, field_changes, _ = self._process_requisitions(requisitions)
            
            _logger.info(
                'Cron Sync Done: %s created, %s updated (%s field changes)',
                created, updated_records, field_changes
            )
        
        except UserError as e:
            _logger.error('Workable requisition cron sync failed: %s', str(e))