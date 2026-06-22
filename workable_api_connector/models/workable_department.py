# -*- coding: utf-8 -*-
from odoo import models, fields, api

class WorkableDepartment(models.Model):
    _name = 'workable.department'
    _description = 'Workable Department'
    _order = 'id'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    department_id = fields.Char(string='Department ID', store=True)
    name = fields.Char(string='Name', store=True)
    parent_id = fields.Char(string='Parent ID', store=True)
    sample = fields.Char(string='Sample', store=True)
    parent_department = fields.Many2one('workable.department', string='Parent Department', store=True)
    test = fields.Text("Text")
