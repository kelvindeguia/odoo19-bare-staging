# -*- coding: utf-8 -*-
import requests
import logging
import time
from datetime import date, datetime

from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

WORKABLE_API_BASE = "https://{subdomain}.workable.com/spi/v3"


class WorkableDepartmentSync(models.Model):
    _inherit = 'workable.department'

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
    # Fetch Department
    # -------------------------------
    # def _fetch_departments_from_workable(self):
    #     token, subdomain = self._get_workable_credentials()

    #     base_url = WORKABLE_API_BASE.format(subdomain=subdomain)
    #     url = f"{base_url}/departments"

    #     headers = {
    #         "Authorization": f"Bearer {token}",
    #         "Accept": "application/json",
    #     }

    #     ICP = self.env['ir.config_parameter'].sudo()
    #     last_sync = ICP.get_param('workable.jobs.last_sync')

    #     params = {
    #         'limit': 100,
    #     }

    #     departments = []
    #     first_call = True
    #     page = 1
        
    #     while url:
    #         _logger.info("Fetching Workable departments - Page %s", page)

    #         response = self._safe_request(
    #             url, 
    #             headers, 
    #             params=params if first_call else None
    #         )
            
    #         first_call = False

    #         try:
    #                 data = response.json()
    #         except ValueError:
    #             raise UserError(f"Invalid JSON response: {response.text}")
            
    #         page_data = data.get('departments', [])
    #         departments.extend(page_data)

    #         _logger.info(
    #             "Fetched %s departments (total so far: %s)", 
    #             len(page_data), len(departments)
    #         )

    #         url = data.get('paging', {}).get('next')
    #         page += 1

    #         if url:
    #             time.sleep(2)

    #     ICP.set_param('workable.departments.last_sync', datetime.utcnow().isoformat())

    #     return departments
    def _fetch_departments_from_workable(self, progress=False):
        token, subdomain = self._get_workable_credentials()

        base_url = WORKABLE_API_BASE.format(subdomain=subdomain)
        url = f"{base_url}/departments"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        ICP = self.env['ir.config_parameter'].sudo()

        params = {
            'limit': 100,
        }

        departments = []
        first_call = True
        page = 1

        while url:
            _logger.info("Fetching Workable departments - Page %s", page)

            response = self._safe_request(
                url,
                headers,
                params=params if first_call else None
            )

            first_call = False

            try:
                data = response.json()
            except ValueError:
                raise UserError(f"Invalid JSON response from Workable: {response.text}")

            if isinstance(data, list):
                page_data = data
                next_url = None

            elif isinstance(data, dict):
                page_data = data.get('departments', [])
                next_url = data.get('paging', {}).get('next')

            else:
                raise UserError(
                    "Unexpected Workable departments response format: %s"
                    % type(data).__name__
                )

            departments.extend(page_data)

            if progress:
                self.env["workable.sync.service"]._update_fetch_count(
                    progress,
                    "Departments",
                    page,
                    len(page_data),
                    len(departments)
                )

            _logger.info(
                "Fetched %s departments (total so far: %s)",
                len(page_data),
                len(departments)
            )

            url = next_url
            page += 1

            if url:
                time.sleep(2)

        ICP.set_param(
            'workable.departments.last_sync',
            datetime.utcnow().isoformat()
        )

        return departments
    
    # -------------------------------
    # Mapping
    # -------------------------------
    def _map_department(self, department):
        """
        Expected Workable department shape is commonly similar to:
        {
            "id": "...",
            "name": "...",
            "parent_id": "...",
            "sample": false
        }

        We only map fields that exist in your current workable.department model.
        """

        workable_department_id = department.get('id')

        return {
            'department_id': workable_department_id or department.get('name'),
            'name': department.get('name') or False,
            'parent_id': department.get('parent_id') or False,
            'sample': str(department.get('sample', False)),
        }

    # -------------------------------
    # Create / Update
    # -------------------------------
    def _process_departments(self, departments):
        created = 0
        updated_records = 0
        field_changes = 0
        changed_fields = []

        for department in departments:
            workable_department_id = department.get('id')

            if not workable_department_id:
                _logger.warning(
                    "Skipping Workable department without ID: %s",
                    department
                )
                continue

            vals = self._map_department(department)

            existing = self.search(
                [('department_id', '=', workable_department_id)],
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
            'Workable departments sync: %d created, %d records updated '
            '(%d fields modified: %s)',
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

            current_value = self._normalize_value(current_value)
            new_value = self._normalize_value(new_value)

            if current_value != new_value and not (
                current_value in (False, None) and new_value in (False, None, '')
            ):
                changes += 1
                changed_fields.append(field)

        return changes, changed_fields

    # -------------------------------
    # Normalize
    # -------------------------------
    def _normalize_value(self, value):
        if isinstance(value, str):
            return value.strip()
        elif hasattr(value, 'strftime'):
            return value.strftime('%Y-%m-%d')
        elif isinstance(value, float):
            return round(value, 6)
        return value

    # -------------------------------
    # Manual Sync
    # -------------------------------
    def action_sync_from_workable(self):
        try:
            departments = self._fetch_departments_from_workable()
            created, updated_records, field_changes, _ = self._process_departments(departments)

            return {
                "params": {
                    "title": "Workable Sync",
                    "message": "Sync Done: %s created, %s updated (%s field changes)" % (
                        created,
                        updated_records,
                        field_changes,
                    ),
                    "type": "success",
                }
            }

        except UserError as e:
            _logger.error("Workable departments sync failed: %s", e)

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
            departments = self._fetch_departments_from_workable()
            created, updated_records, field_changes, _ = self._process_departments(departments)

            _logger.info(
                'Workable departments cron sync done: %s created, %s updated '
                '(%s field changes)',
                created,
                updated_records,
                field_changes
            )

        except UserError as e:
            _logger.error(
                'Workable departments cron sync failed: %s',
                str(e)
            )