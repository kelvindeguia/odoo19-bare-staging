# -*- coding: utf-8 -*-
from odoo import models, fields, api


class WorkableHiringPlan(models.Model):
    _name = 'workable.hiring.plan'
    _description = 'Workable Hiring Plan'
    _order = 'id'
    _rec_name = 'requisition_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    requisition_id = fields.Char(string='Requisition ID', required=True, store=True)
    workable_requisition_id = fields.Char(string='Workable Requisition ID', store=True)
    status = fields.Selection([
        ('open', 'Open'),
        ('processing', 'Processing'),
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('reserved', 'Reserved'),
        ('on_hold', 'On Hold'),
        ('filled', 'Filled'),
        ('approved', 'Approved'),
        ('closed', 'Closed')
    ], string='Status', default='open')
    job_title = fields.Char(string='Job Title', store=True)
    workable_job_id = fields.Char(string='Workable Job ID', store=True)
    department = fields.Char(string='Department', store=True)
    workable_department_id = fields.Char(string='Workable Department ID', store=True)
    requisition_location = fields.Char(string='Requisition Location', store=True)
    hiring_manager = fields.Char(string='Hiring Manager', store=True)
    requisition_owner = fields.Char(string='Requisition Owner', store=True)
    plan_date = fields.Date(string='Plan Date', store=True)
    reason = fields.Selection([
        ('new_hire', 'New Hire'),
        ('replacement', 'Replacement'),
        ('backfill', 'Backfill')
    ], string='Reason', default='new_hire', store=True)
    employment_type = fields.Selection([
        ('full_time', 'Full-time'),
        ('part_time', 'Part-time'),
        ('contract', 'Contract'),
        ('temporary', 'Temporary'),
        ('other', 'Other')
    ], string='Employment Type', default='full_time', store=True)
    experience = fields.Selection([
        ('not_applicable', 'Not Applicable'),
        ('internship', 'Internship'),
        ('entry_level', 'Entry Level'),
        ('associate', 'Associate'),
        ('mid_senior_level', 'Mid-Senior Level'),
        ('director', 'Director'),
        ('executive', 'Executive')
    ], string='Experience', default='entry_level', store=True)
    salary_from = fields.Float(string='Salary Range - From', store=True)
    salary_to = fields.Float(string='Salary Range - To', store=True)
    salary_currency = fields.Char(string='Salary Range - Currency', store=True)
    salary_frequency = fields.Char(string='Salary Range - Frequency', store=True)
    salary_package_currency = fields.Char(string='Salary Package - Currency', store=True)
    salary_package_frequency = fields.Char(string='Salary Package - Frequency', store=True)

    # Binary Fields
    calibration_notes = fields.Binary(string="Calibration Notes", store=True)
    calibration_notes_url = fields.Char(string="Calibration Notes URL", store=True)
    job_description = fields.Binary(string="Job Description", store=True)

    # Date Fields
    created_on = fields.Date(string="Created On", store=True)
    sourcing_date = fields.Date(string="Sourcing Date", store=True)
    calibration_date = fields.Date(string="Calibration Date", store=True)
    target_start_date = fields.Date(string="Target Start Date", store=True)

    # Selection Fields
    company = fields.Selection([
        ('onsite_isupport','Onsite (iSupport)'), 
        ('onsite_iswerk','Onsite (iSwerk)'), 
        ('hybrid_iswerk','Hybrid (iSwerk)'),
        ('wfh_swerk','WFH (iSwerk)')], string="Company", store=True)
    client_business_category = fields.Selection([
        ('client_services','Client Services'),
        ('sales','Sales'),
        ('na','N/A')], string="Client-Business Category", store=True)
    career_level = fields.Selection([
        ('rank_and_file','Rank and File'),
        ('Managerial','Managerial'),
        ('executive','Executive')], string="Career Level", store=True)
    client_classification = fields.Selection([
        ('client_services','Client Services'),
        ('sales','Sales'),
        ('support_hiring','Support Hiring')], string="Client Classification", store=True)
    job_classification = fields.Selection([
        ('generic','Generic'),
        ('niche','Niche'),
        ('tech','Tech'),
        ('support','Support')], string="Job Classification", store=True)
    position_classification = fields.Selection([
        ('organica_growth','Organic/Growth'),
        ('new','New'),
        ('layup','Layup'),
        ('backfill','Backfill'),
        ('support_hiring','Support Hiring')], string="Position Classification", store=True)

    # Char Fields
    industry = fields.Char(string="Industry", store=True)
    client_website = fields.Char(string="Client Website", store=True)
    department_head = fields.Char(string="Department Head", store=True)
    requestor = fields.Char(string="Requestor", store=True)
    sales_lead = fields.Char(string="Sales Lead", store=True)
    hiring_manager_client = fields.Char(string="Hiring Manager - Client", store=True)
    hiring_manager_email_client = fields.Char(string="Hiring Manager Email - Client", store=True)
    secondary_hiring_manager_poc = fields.Char(string="Secondary Hiring Manager POC", store=True)
    night_differential = fields.Char(string="Night Differential", store=True)
    hiring_manager_client_2 = fields.Char(string="Hiring Manager - Client 2", store=True)
    hiring_manager_email_client_2 = fields.Char(string="Hiring Manager Email - Client 2", store=True)
    hiring_manager_client_3 = fields.Char(string="Hiring Manager - Client 3", store=True)
    hiring_manager_email_client_3 = fields.Char(string="Hiring Manager Email - Client 3", store=True)
    candidate = fields.Char(string="Candidate", store=True)
    approved_by = fields.Char(string="Approved By", store=True)

    # Float Fields
    salary_package = fields.Float(string="Salary Package", store=True)
    allowances = fields.Float(string="Allowances", store=True)
    bonuses = fields.Float(string="Bonuses", store=True)
    incentives = fields.Float(string="Incentives", store=True)
    life_insurance = fields.Float(string="Life Insurance", store=True)

    # Text Fields
    salary_package_remarks = fields.Text(string="Salary Package Remarks", store=True)

    # Integer Fields
    headcount_demand = fields.Integer(string="Headcount Demand", store=True)
    remaining_vacancy = fields.Integer(string="Remaining Vacancy", store=True)
    requisition_age = fields.Integer(string="Requisition Age", store=True)
    headcount = fields.Integer(string="Headcount", store=True)

    # workable short code
    workable_shortcode = fields.Char(string='Workable Shortcode', store=True, index=True, copy=False,)

    # Many2one Fields
    department_id = fields.Many2one('workable.department', string='Department', store=True)
    job_id = fields.Many2one('workable.job', string='Job', store=True)