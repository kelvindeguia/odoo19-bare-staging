# -*- coding: utf-8 -*-
from odoo import models, fields, api


class WorkableEmployee(models.Model):
    _name = 'workable.employees'
    _description = 'Workable Employee'
    _order = 'id'
    _rec_name = 'employee_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    employee_id = fields.Char(string='Employee ID', required=True, store=True)
    first_name = fields.Char(string='First Name', store=True)
    middle_name = fields.Char(string='Middle Name', store=True)
    last_name = fields.Char(string='Last Name', store=True)
    preferred_name = fields.Char(string='Preferred Name', store=True)
    state = fields.Selection([('draft', 'Draft'), ('active', 'Active'), ('inactive', 'Inactive'), ('published', 'Published')], string='Status', default='draft', store=True)
    country = fields.Char(string='Country', store=True)
    address = fields.Char(string='Address', store=True)
    gender = fields.Selection([('male', 'Male'), ('female', 'Female'), ('other', 'Other')], string='Gender', store=True)
    birthdate = fields.Date(string='Birthdate', store=True)
    marital_status = fields.Selection([('single', 'Single'), ('married', 'Married'), ('divorced', 'Divorced'), ('widowed', 'Widowed')], string='Marital Status', store=True)
    certificate_url = fields.Char(string='Certificate URL', store=True)
    phone_type = fields.Selection([('mobile', 'Mobile'), ('home', 'Home'), ('work', 'Work')], string='Phone Type', store=True)
    phone = fields.Char(string='Phone', store=True)
    extension = fields.Char(string='Extension', store=True)
    work_email = fields.Char(string='Work Email', store=True)
    personal_email = fields.Char(string='Personal Email', store=True)
    chat_video_communication = fields.Boolean(string='Chat/Video Communication', store=True)
    social_media = fields.Char(string='Social Media', store=True)
    job_title = fields.Char(string='Job Title', store=True)
    hire_date = fields.Date(string='Hire Date', store=True)
    start_date = fields.Date(string='Start Date', store=True)
    entity = fields.Char(string='Entity', store=True)
    department = fields.Char(string='Department', store=True)
    division = fields.Char(string='Division', store=True)
    manager = fields.Char(string='Manager', store=True)
    effective_date = fields.Date(string='Effective Date', store=True)
    employment_type = fields.Selection([('full_time', 'Full Time'), ('part_time', 'Part Time'), ('contractor', 'Contractor')], string='Employment Type', store=True)
    workplace = fields.Char(string='Workplace', store=True)
    expiry_date = fields.Date(string='Expiry Date', store=True)
    note = fields.Text(string='Note', store=True)
    work_schedule = fields.Char(string='Work Schedule', store=True)
    work_effective_date = fields.Date(string='Effective Date', store=True)
    pay_type = fields.Selection([('salary', 'Salary'), ('hourly', 'Hourly')], string='Pay Type', store=True)
    currency = fields.Char(string='Currency', store=True)
    amount = fields.Float(string='Amount', store=True)
    frequency = fields.Selection([('weekly', 'Weekly'), ('bi_weekly', 'Bi-Weekly'), ('monthly', 'Monthly')], string='Frequency', store=True)
    pay_schedule = fields.Char(string='Pay Schedule', store=True)
    overtime_status = fields.Boolean(string='Overtime Status', store=True)
    reason = fields.Text(string='Reason', store=True)
    overtime_note = fields.Text(string='Overtime Note', store=True)

    workable_employee_id = fields.Char(string='Workable Employee ID', store=True)
    department_id = fields.Many2one('workable.department', string="Department", store=True)
    job_id = fields.Many2one('workable.job', string="Job", store=True)