# -*- coding: utf-8 -*-

import logging
import threading

from odoo import api, models, _
from odoo.exceptions import UserError
from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)


class WorkableSyncService(models.TransientModel):
    _name = "workable.sync.service"
    _description = "Workable Sync Service"

    @api.model
    def action_start_sync_all_from_workable(self):
        progress = self.env["workable.sync.progress"].sudo().create({
            "name": "Workable Sync",
            "state": "pending",
            "current_step": "Preparing Workable sync...",
            "progress": 0,
            "message": "Preparing Workable sync...",
            "summary_logs": "",
        })

        db_name = self.env.cr.dbname
        uid = self.env.uid
        context = dict(self.env.context)
        progress_id = progress.id

        thread = threading.Thread(
            target=self._run_sync_all_in_background,
            args=(db_name, uid, context, progress_id),
            daemon=True,
        )
        thread.start()

        return {
            "progress_id": progress_id,
            "params": {
                "title": _("Workable Sync Started"),
                "message": _("Workable sync is now running."),
                "type": "info",
            }
        }

    def _run_sync_all_in_background(self, db_name, uid, context, progress_id):
        registry = Registry(db_name)

        with registry.cursor() as cr:
            env = api.Environment(cr, uid, context)
            service = env["workable.sync.service"].sudo()
            progress = env["workable.sync.progress"].sudo().browse(progress_id)

            try:
                service._update_progress(
                    progress,
                    "Starting Workable sync",
                    1,
                    "Starting Workable sync...",
                    state="running"
                )

                service._sync_departments(progress)
                service._sync_jobs(progress)
                service._sync_hiring_plans(progress)
                service._sync_candidates(progress)
                service._sync_employees(progress)

                service._update_progress(
                    progress,
                    "Completed",
                    100,
                    "Workable sync completed successfully.",
                    state="done"
                )

                progress.sudo().write({
                    "show_report": True,
                })
                cr.commit()

            except Exception as e:
                _logger.exception("Background Workable sync failed")
                service._update_progress(
                    progress,
                    "Failed",
                    progress.progress or 0,
                    str(e),
                    state="failed"
                )

    @api.model
    def action_get_sync_progress(self, progress_id):
        progress = self.env["workable.sync.progress"].sudo().browse(progress_id)

        if not progress.exists():
            return {
                "state": "failed",
                "current_step": "Missing Progress Record",
                "progress": 0,
                "message": "The sync progress record no longer exists.",
                "current_model": "",
                "current_page": 0,
                "current_batch_count": 0,
                "current_total_fetched": 0,
                "logs": progress.summary_logs or "",
                "report_data": progress.report_data or {},
                "show_report": progress.show_report,
            }

        return {
            "state": progress.state,
            "current_step": progress.current_step,
            "progress": progress.progress,
            "message": progress.message or "",
            "current_model": progress.current_model or "",
            "current_page": progress.current_page or 0,
            "current_batch_count": progress.current_batch_count or 0,
            "current_total_fetched": progress.current_total_fetched or 0,
            "logs": progress.summary_logs or "",
            "report_data": progress.report_data or {},
            "show_report": progress.show_report,
        }

    def _update_progress(self, progress, step, percentage, message=False, state="running"):
        progress.sudo().write({
            "state": state,
            "current_step": step,
            "progress": percentage,
            "message": message or step,
        })
        self.env.cr.commit()

    def _update_fetch_count(self, progress, model_name, page, batch_count, total_fetched):
        progress.sudo().write({
            "current_model": model_name,
            "current_page": page,
            "current_batch_count": batch_count,
            "current_total_fetched": total_fetched,
            "message": "Fetched %s %s records so far" % (total_fetched, model_name),
        })
        self.env.cr.commit()

    def _update_report_data(self, progress, model_key, model_label, created, updated, field_changes, updated_fields):
        report_data = progress.report_data or {}

        report_data[model_key] = {
            "label": model_label,
            "created": created,
            "updated": updated,
            "field_changes": field_changes,
            "updated_fields": updated_fields or [],
        }

        progress.sudo().write({
            "report_data": report_data,
        })
        self.env.cr.commit()

    def _add_summary_log(self, progress, message):
        current_logs = progress.summary_logs or ""
        progress.sudo().write({
            "summary_logs": current_logs + message + "\n",
            "message": message,
        })
        self.env.cr.commit()

    def _sync_departments(self, progress):
        self._update_progress(
            progress,
            "Syncing Departments",
            10,
            "Fetching departments from Workable..."
        )

        model = self.env["workable.department"]
        departments = model._fetch_departments_from_workable(progress=progress)
        created, updated, changes, updated_fields = model._process_departments(departments)

        message = "Departments: %s created, %s updated, %s field changes" % (
            created, updated, changes
        )

        self._update_report_data(
            progress,
            "departments",
            "Departments",
            created,
            updated,
            changes,
            updated_fields
        )

        self._add_summary_log(progress, message)
        self._update_progress(progress, "Departments Completed", 25, message)

    def _sync_jobs(self, progress):
        self._update_progress(
            progress,
            "Syncing Jobs",
            35,
            "Fetching jobs from Workable..."
        )

        model = self.env["workable.job"]
        jobs = model._fetch_jobs_from_workable(progress=progress)
        created, updated, changes, updated_fields = model._process_jobs(jobs)

        message = "Jobs: %s created, %s updated, %s field changes" % (
            created, updated, changes
        )

        self._update_report_data(
            progress,
            "jobs",
            "Jobs",
            created,
            updated,
            changes,
            updated_fields
        )

        self._add_summary_log(progress, message)
        self._update_progress(progress, "Jobs Completed", 50, message)

    def _sync_hiring_plans(self, progress):
        self._update_progress(
            progress,
            "Syncing Hiring Plans",
            60,
            "Fetching requisitions from Workable..."
        )

        model = self.env["workable.hiring.plan"]
        requisitions = model._fetch_workable_requisitions(progress=progress)
        created, updated, changes, updated_fields = model._process_requisitions(requisitions)

        message = "Hiring Plans: %s created, %s updated, %s field changes" % (
            created, updated, changes
        )

        self._update_report_data(
            progress,
            "hiring_plans",
            "Hiring Plans",
            created,
            updated,
            changes,
            updated_fields
        )

        self._add_summary_log(progress, message)
        self._update_progress(progress, "Hiring Plans Completed", 75, message)

    def _sync_candidates(self, progress):
        self._update_progress(
            progress,
            "Syncing Candidates",
            80,
            "Fetching candidates from Workable..."
        )

        model = self.env["workable.candidate"]
        candidates = model._fetch_candidates_from_workable(progress=progress)
        created, updated, failed, updated_fields = model._process_candidates(
            candidates,
            fetch_details=False,
            source="api",
            progress=progress,
        )

        message = "Candidates: %s created, %s updated, %s failed" % (
            created, updated, failed
        )

        self._update_report_data(
            progress,
            "candidates",
            "Candidates",
            created,
            updated,
            failed,
            updated_fields
        )

        self._add_summary_log(progress, message)
        self._update_progress(progress, "Candidates Completed", 82, message)

    def _sync_employees(self, progress):
        self._update_progress(
            progress,
            "Syncing Employees",
            85,
            "Fetching employees from Workable..."
        )

        model = self.env["workable.employees"]
        employees = model._fetch_workable_employees(progress=progress)
        created, updated, changes, updated_fields = model._process_employees(employees)

        message = "Employees: %s created, %s updated, %s field changes" % (
            created, updated, changes
        )

        self._update_report_data(
            progress,
            "employees",
            "Employees",
            created,
            updated,
            changes,
            updated_fields
        )

        self._add_summary_log(progress, message)
        self._update_progress(progress, "Employees Completed", 95, message)

    @api.model
    def cron_sync_all_from_workable(self):
        progress = self.env["workable.sync.progress"].sudo().create({
            "name": "Scheduled Workable Sync",
            "state": "running",
            "current_step": "Starting scheduled Workable sync...",
            "progress": 0,
            "message": "Starting scheduled sync...",
        })

        self._sync_departments(progress)
        self._sync_jobs(progress)
        self._sync_hiring_plans(progress)
        self._sync_candidates(progress)
        self._sync_employees(progress)

        self._update_progress(
            progress,
            "Completed",
            100,
            "Scheduled Workable sync completed successfully.",
            state="done"
        )