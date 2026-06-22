# -*- coding: utf-8 -*-
import requests
import logging
import time
from datetime import date, datetime

from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

WORKABLE_API_BASE = "https://{subdomain}.workable.com/spi/v3"


class WorkableEmployeesSync(models.Model):
    _inherit = 'workable.employees'

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
    # Safe Request with Retry (429 FIX)
    # -------------------------------
    def _safe_request(self, url, headers, params=None):
        max_retries = 5
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers, params=params, timeout=30)

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
    # Fetch Employees
    # -------------------------------
    def _fetch_workable_employees(self, progress=False):
        token, subdomain = self._get_workable_credentials()

        base_url = WORKABLE_API_BASE.format(subdomain=subdomain)
        url = f"{base_url}/employees"

        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
        }

        ICP = self.env['ir.config_parameter'].sudo()
        last_sync = ICP.get_param('workable.employees.last_sync')

        params = {
            'limit': 100,
        }

        employees = []
        first_call = True
        page = 1

        while url:
            _logger.info("Fetching Workable Employees page %s", page)

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

            page_data = data.get('employees', [])
            employees.extend(page_data)
            
            if progress:
                self.env["workable.sync.service"]._update_fetch_count(
                    progress,
                    "Employees",
                    page,
                    len(page_data),
                    len(employees)
                )

            _logger.info(
                "Fetched %s employees (total so far: %s)",
                len(page_data), len(employees)
            )

            url = data.get('paging', {}).get('next')
            page += 1

            if url:
                time.sleep(2)

        ICP.set_param('workable.employees.last_sync', datetime.utcnow().isoformat())

        return employees

    def _find_department_from_employee(self, employee):
        employee_department_value = (
            employee.get('department')
            or employee.get('department_id')
            or employee.get('department_name')
            or False
        )

        if not employee_department_value:
            return False

        if isinstance(employee_department_value, dict):
            employee_department_value = (
                employee_department_value.get('id')
                or employee_department_value.get('name')
                or False
            )

        if not employee_department_value:
            return False

        employee_department_value = str(employee_department_value).strip()

        department_rec = self.env['workable.department'].search(
            [('department_id', '=', employee_department_value)],
            limit=1
        )

        return department_rec.id if department_rec else False


    def _find_job_from_employee(self, employee):
        workable_job_id = employee.get('job_id') or employee.get('workable_job_id')
        job_title = employee.get('job_title')

        if workable_job_id:
            job_rec = self.env['workable.job'].search(
                [('workable_job_id', '=', workable_job_id)],
                limit=1
            )
            if job_rec:
                return job_rec.id

        if job_title:
            job_rec = self.env['workable.job'].search(
                [('title', '=', job_title)],
                limit=1
            )
            if job_rec:
                return job_rec.id

        return False

    # -------------------------------
    # Mapping
    # -------------------------------
    def _map_employees(self, employee):
        start_date_str = employee.get('start_date')
        start_date = start_date_str[:10] if start_date_str else False

        birthdate_str = employee.get('birthdate')
        birthdate = birthdate_str[:10] if birthdate_str else False

        state_value = employee.get('state') or False
        status_semantic = employee.get('status_semantic_type')

        if state_value == 'published':
            state = 'published'
        elif status_semantic == 'status_active':
            state = 'active'
        else:
            state = 'draft'

        phone = employee.get('phone')
        phone_type = 'work' if phone else False

        department_data = employee.get('department') or employee.get('department_id') or ''
        department_name = department_data.get('name') if isinstance(department_data, dict) else department_data
        job_title = employee.get('job_title', '')

        return {
            'employee_id': employee.get('employee_number') or employee.get('id'),
            'workable_employee_id': employee.get('id'),
            'first_name': employee.get('firstname', ''),
            'last_name': employee.get('lastname', ''),
            'preferred_name': employee.get('preferred_name', ''),
            'state': state,
            'birthdate': birthdate,
            'phone': phone or '',
            'phone_type': phone_type,
            'work_email': employee.get('work_email', ''),
            'personal_email': employee.get('email', ''),
            'job_title': job_title,
            'start_date': start_date,
            'hire_date': start_date,
            'employment_type': 'full_time',

            # defaults
            'middle_name': '',
            'country': '',
            'address': '',
            'gender': False,
            'marital_status': False,
            'certificate_url': '',
            'extension': '',
            'chat_video_communication': False,
            'social_media': '',
            'entity': '',
            'department': department_name or '',
            'department_id': self._find_department_from_employee(employee),
            'job_id': self._find_job_from_employee(employee),
            'division': '',
            'manager': '',
            'effective_date': False,
            'workplace': '',
            'expiry_date': False,
            'note': '',
            'work_schedule': '',
            'work_effective_date': False,
            'pay_type': False,
            'currency': '',
            'amount': 0.0,
            'frequency': False,
            'pay_schedule': '',
            'overtime_status': False,
            'reason': '',
            'overtime_note': '',
        }

    # -------------------------------
    # Create / Update
    # -------------------------------
    def _process_employees(self, employees):
        created = updated_records = field_changes = 0
        changed_fields = []

        for emp in employees:
            employee_id = emp.get('id')
            if not employee_id:
                continue

            vals = self._map_employees(emp)

            existing = self.search(
                [('workable_employee_id', '=', employee_id)],
                limit=1
            )

            if existing:
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
            'Workable employees sync: %d created, %d records updated (%d fields modified: %s)',
            created, updated_records, field_changes,
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
                    "Detected change on %s ID %s | field=%s | current=%r | new=%r",
                    record._name,
                    record.id,
                    field,
                    normalized_current,
                    normalized_new,
                )

                changes += 1
                changed_fields.append(field)

        return changes, changed_fields

    # -------------------------------
    # Normalize
    # -------------------------------
    def _normalize_value(self, value):

        # Empty values
        if value in (None, '', False):
            return False

        # Many2one from Odoo read(): [id, display_name]
        if isinstance(value, list) and len(value) == 2 and isinstance(value[0], int):
            return value[0]

        # Many2one from Odoo read(): (id, display_name)
        if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], int):
            return value[0]

        # Datetime object
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%d %H:%M:%S')

        # Date object
        if isinstance(value, date):
            return value.strftime('%Y-%m-%d')

        # String
        if isinstance(value, str):
            value = value.strip()

            if not value:
                return False

            # Normalize ISO datetime from API
            if value.endswith('Z'):
                value = value.replace('T', ' ').replace('Z', '')

            if 'T' in value:
                value = value.replace('T', ' ')
                value = value[:19]

            return value

        # Float
        if isinstance(value, float):
            return round(value, 6)

        return value

    # -------------------------------
    # Manual Sync (FIXED)
    # -------------------------------
    def action_sync_from_workable(self):
        try:
            employees = self._fetch_workable_employees()
            created, updated_records, field_changes, _ = self._process_employees(employees)

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
            _logger.error("Workable employees sync failed: %s", e)
            return {
                "params": {
                    "title": _("Workable Sync Error"),
                    "message": str(e),
                    "type": "danger",
                }
            }

    # -------------------------------
    # Cron (FIXED)
    # -------------------------------
    @api.model
    def cron_sync_from_workable(self):
        try:
            employees = self._fetch_workable_employees()
            created, updated_records, field_changes, _ = self._process_employees(employees)

            _logger.info(
                'Cron Sync Done: %s created, %s updated (%s field changes)',
                created, updated_records, field_changes
            )

        except UserError as e:
            _logger.error('Workable employees cron sync failed: %s', str(e))