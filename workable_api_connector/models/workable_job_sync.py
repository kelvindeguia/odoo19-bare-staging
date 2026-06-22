# -*- coding: utf-8 -*-
import requests
import logging
import time
from datetime import date, datetime

from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

WORKABLE_API_BASE = "https://{subdomain}.workable.com/spi/v3"


class WorkableJobSync(models.Model):
    _inherit = 'workable.job'

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
    # Fetch Jobs
    # -------------------------------
    def _fetch_jobs_from_workable(self, progress=False):
        token, subdomain = self._get_workable_credentials()

        base_url = WORKABLE_API_BASE.format(subdomain=subdomain)
        url = f"{base_url}/jobs"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        ICP = self.env['ir.config_parameter'].sudo()
        last_sync = ICP.get_param('workable.jobs.last_sync')

        params = {
            'limit': 100,
        }

        jobs = []
        first_call = True
        page = 1
        
        while url:
            _logger.info("Fetching Workable jobs - Page %s", page)

            response = self._safe_request(
                url, 
                headers, 
                params=params if first_call else None
            )
            
            first_call = False

            try:
                    data = response.json()
            except ValueError:
                raise UserError(f"Invalid JSON response: {response.text}")
            
            page_data = data.get('jobs', [])
            jobs.extend(page_data)

            if progress:
                self.env["workable.sync.service"]._update_fetch_count(
                    progress,
                    "Jobs",
                    page,
                    len(page_data),
                    len(jobs)
                )

            _logger.info(
                "Fetched %s jobs (total so far: %s)", 
                len(page_data), len(jobs)
            )

            url = data.get('paging', {}).get('next')
            page += 1

            if url:
                time.sleep(2)

        ICP.set_param('workable.jobs.last_sync', datetime.utcnow().isoformat())

        return jobs
    
    # -------------------------------
    # Mapping
    # -------------------------------
    # def _map_jobs(self, job):
    #     job_id = job.get('id')
    #     title = job.get('title')

    #     return {
    #         'job_id': job.get('shortcode') or job.get('id'),
    #         'workable_job_id': job.get('id'),
    #         'title': job.get('title'),
    #         'full_title': job.get('full_title'),
    #         'shortcode': job.get('shortcode'),
    #         'state': job.get('state'),
    #         'confidential': job.get('confidential', False),
    #         'department_id': job.get('department', {}).get('id') if job.get('department') else None,
    #         'department_hierarchy_id': job.get('department_hierarchy', {}).get('id') if job.get('department_hierarchy') else None,
    #         'url': job.get('url'),
    #         'application_url': job.get('application_url'),
    #         'shortlink': job.get('shortlink'),
    #         'workplace_type': job.get('workplace_type'),
    #         'job_location': job.get('location', {}).get('name') if job.get('location') else None,
    #         'salary_currency': job.get('salary', {}).get('currency') if job.get('salary') else None,
    #         'created_at': job.get('created_at'),
    #         'updated_at': job.get('updated_at'),

    #         #defaults
    #         'hidden': False,
    #         'telecommuting': False,

    #     }
    def _map_jobs(self, job):
        # location = job.get('location') or {}
        # salary = job.get('salary') or {}
        department = job.get('department')
        department_hierarchy_id = job.get('department_hierarchy')

        vals = {
            'job_id': job.get('shortcode') or job.get('id'),
            'workable_job_id': job.get('id') or False,
            'shortcode': job.get('shortcode') or False,

            'title': job.get('title') or False,
            'full_title': job.get('full_title') or False,
            'code': job.get('code') or False,
            'state': job.get('state') or False,
            # 'sample': bool(job.get('sample', False)),
            'confidential': bool(job.get('confidential', False)),

            'url': job.get('url') or False,
            'application_url': job.get('application_url') or False,
            'shortlink': job.get('shortlink') or False,

            'workplace_type': job.get('workplace_type') or False,

            # 'location_str': location.get('location_str') or False,
            # 'location_country': location.get('country') or False,
            # 'location_country_code': location.get('country_code') or False,
            # 'location_region': location.get('region') or False,
            # 'location_region_code': location.get('region_code') or False,
            # 'location_city': location.get('city') or False,
            # 'location_zip_code': location.get('zip_code') or False,
            # 'telecommuting': bool(location.get('telecommuting', False)),

            # 'salary_currency': salary.get('salary_currency') or False,

            # 'created_at': job.get('created_at') or False,
            # 'updated_at': job.get('updated_at') or False,
            # 'keywords': job.get('keywords') or False,
            'created_at': self._to_odoo_datetime(job.get('created_at')),
            'updated_at': self._to_odoo_datetime(job.get('updated_at')),
            # 'keywords': self._normalize_keywords(job.get('keywords')),
        }

        if department:
            if isinstance(department, dict):
                vals['department'] = department.get('name') or False
            else:
                vals['department'] = department

            # Auto-match department_id from workable.department model
            vals['department_id'] = self._find_department_by_name(vals['department'])

        if department_hierarchy_id is not None:
            vals['department_hierarchy_id'] = str(department_hierarchy_id)

        return vals
    
    # -------------------------------
    # Find Department by Name
    # -------------------------------
    def _find_department_by_name(self, department_name):
        """Search for a department by name and return its ID."""
        if not department_name:
            return False

        department = self.env['workable.department'].search(
            [('name', '=', department_name)],
            limit=1
        )

        if department:
            _logger.debug("Matched department '%s' to ID %s", department_name, department.id)
            return department.id

        _logger.warning("Department '%s' not found in workable.department", department_name)
        return False
    
        # mapped_jobs = []
        # for job in jobs:
        #     mapped = {
        #         'job_id': job.get('id'),
        #         'title': job.get('title'),
        #         'full_title': job.get('full_title'),
        #         'shortcode': job.get('shortcode'),
        #         'state': job.get('state'),
        #         'confidential': job.get('confidential', False),
        #         'department_id': job.get('department', {}).get('id') if job.get('department') else None,
        #         'department_hierarchy_id': job.get('department_hierarchy', {}).get('id') if job.get('department_hierarchy') else None,
        #         'url': job.get('url'),
        #         'application_url': job.get('application_url'),
        #         'shortlink': job.get('shortlink'),
        #         'workplace_type': job.get('workplace_type'),
        #         'job_location': job.get('location', {}).get('name') if job.get('location') else None,
        #         'salary_currency': job.get('salary', {}).get('currency') if job.get('salary') else None,
        #         'created_at': job.get('created_at'),
        #         'updated_at': job.get('updated_at'),
        #     }
        #     mapped_jobs.append(mapped)
        # return mapped_jobs
    
    # -------------------------------
    # Create / Update
    # -------------------------------
    # def _process_jobs(self, jobs):
    #     created = updated_records = field_changes = 0
    #     changed_fields = []

    #     for job in jobs:
    #         job_id = job.get('id')
    #         if not job_id:
    #             continue

    #         vals = self._map_jobs(job)

    #         existing = self.search(
    #             [('workable_job_id', '=', job_id)],
    #         )

    #         if existing:
    #             changes_count, fields_list = self._count_changes(existing, vals)
    #             if changes_count > 0:
    #                 existing.write(vals)
    #                 updated_records += 1
    #                 field_changes += changes_count
    #                 changed_fields.extend(fields_list)
    #         else:
    #             self.create(vals)
    #             created += 1

    #     unique_fields = list(set(changed_fields))

    #     _logger.info(
    #         'Workable jobs sync: %d created, %d records updated (%d fields modified: %s)',
    #         created, updated_records, field_changes,
    #         ', '.join(unique_fields) if unique_fields else 'none'
    #     )

    #     return created, updated_records, field_changes, unique_fields
    def _process_jobs(self, jobs):
        created = updated_records = field_changes = 0
        changed_fields = []

        for job in jobs:
            workable_id = job.get('id')
            if not workable_id:
                continue

            vals = self._map_jobs(job)

            existing = self.search(
                [('workable_job_id', '=', workable_id)],
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
                _logger.info(
                    "JOB DATETIME CHECK | created_at=%s | updated_at=%s",
                    vals.get('created_at'),
                    vals.get('updated_at')
                )
                self.create(vals)
                created += 1

        unique_fields = sorted(list(set(changed_fields)))

        _logger.info(
            'Workable jobs sync: %d created, %d records updated (%d fields modified: %s)',
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

    # def _normalize_keywords(self, keywords):
    #     if not keywords:
    #         return False

    #     if isinstance(keywords, list):
    #         cleaned_keywords = [
    #             str(keyword).strip()
    #             for keyword in keywords
    #             if keyword not in (None, '', False)
    #         ]
    #         return ', '.join(sorted(cleaned_keywords)) if cleaned_keywords else False

    #     if isinstance(keywords, str):
    #         cleaned_keywords = [
    #             keyword.strip()
    #             for keyword in keywords.split(',')
    #             if keyword.strip()
    #         ]
    #         return ', '.join(sorted(cleaned_keywords)) if cleaned_keywords else False

    #     return str(keywords).strip() or False

    # -------------------------------
    # Manual Sync (FIXED)
    # -------------------------------
    def action_sync_from_workable(self):
        try:
            jobs = self._fetch_jobs_from_workable()
            created, updated_records, field_changes, _ = self._process_jobs(jobs)

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
            _logger.error("Workable jobs sync failed: %s", e)
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
    # @api.model
    # def cron_sync_from_workable(self):
    #     try:
    #         jobs = self._fetch_workable_jobs()
    #         created, updated_records, field_changes, _ = self._process_jobs(jobs)

    #         _logger.info(
    #             'Cron Sync Done: %s created, %s updated (%s field changes)',
    #             created, updated_records, field_changes
    #         )

    #     except UserError as e:
    #         _logger.error('Workable jobs cron sync failed: %s', str(e))
    @api.model
    def cron_sync_from_workable(self):
        try:
            jobs = self._fetch_jobs_from_workable()
            created, updated_records, field_changes, _ = self._process_jobs(jobs)

            _logger.info(
                'Cron Sync Done: %s created, %s updated (%s field changes)',
                created, updated_records, field_changes
            )

        except UserError as e:
            _logger.error('Workable jobs cron sync failed: %s', str(e))
    # -------------------------------
    # Convert Workable Datetime to Odoo Datetime
    # -------------------------------
    def _to_odoo_datetime(self, value):
        if not value:
            return False

        if not isinstance(value, str):
            return value

        value = value.strip()

        # Workable example:
        # 2026-02-25T14:38:50Z
        try:
            if value.endswith('Z'):
                value = value.replace('T', ' ').replace('Z', '')
                dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                return dt.strftime('%Y-%m-%d %H:%M:%S')

            if 'T' in value:
                value = value.replace('T', ' ')
                if '+' in value:
                    value = value.split('+')[0]
                dt = datetime.strptime(value[:19], '%Y-%m-%d %H:%M:%S')
                return dt.strftime('%Y-%m-%d %H:%M:%S')

            return value

        except Exception:
            raise UserError(f"Invalid datetime format from Workable: {value}")