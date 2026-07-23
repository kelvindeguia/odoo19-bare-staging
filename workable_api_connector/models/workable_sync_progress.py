# -*- coding: utf-8 -*-

from odoo import fields, models


class WorkableSyncProgress(models.TransientModel):
    _name = "workable.sync.progress"
    _description = "Workable Sync Progress"

    name = fields.Char(default="Workable Sync")

    state = fields.Selection([
        ("pending", "Pending"),
        ("running", "Running"),
        ("done", "Done"),
        ("failed", "Failed"),
    ], default="pending")

    current_step = fields.Char(default="Preparing sync...")
    progress = fields.Integer(default=0)
    message = fields.Text()

    current_model = fields.Char()
    current_page = fields.Integer(default=0)
    current_batch_count = fields.Integer(default=0)
    current_total_fetched = fields.Integer(default=0)

    summary_logs = fields.Text(default="")

    report_data = fields.Json(default={})
    show_report = fields.Boolean(default=False)