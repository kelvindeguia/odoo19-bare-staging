from odoo import models, fields
from datetime import time,datetime,date
from odoo.exceptions import UserError

class InfraDashboard(models.Model):
    _name = 'lighthouse.report.overview'
    _description = 'Helpdesk Lighthouse Reports'

    name = fields.Char(default=lambda self: f"IHelpdesk Lighthouse Report - {date.today()}")

    _rec_name = 'name'

    lighthouse_report_created_by = fields.Many2one(
        'res.users',
        string="Created By",
        default=lambda self: self.env.user,
        readonly=True
    )
    
    lighthouse_report_created_on = fields.Datetime(
        string="Created On",
        default=fields.Datetime.now,
        readonly=True
    )

    lighthouse_report_date = fields.Date(
        string="Date"
    )

    new_tickets = fields.Integer(string="New Tickets")
    on_hold_tickets = fields.Integer(string="On Hold Tickets")
    closed_tickets = fields.Integer(string="Closed Tickets")

    backlog = fields.Integer(string="Backlog")
    good = fields.Integer(string="Good")
    okay = fields.Integer(string="Okay")
    bad = fields.Integer(string="Bad")
    
    first_response_time = fields.Char(string="First Response Time")
    response_time = fields.Char(string="Response Time")
    resolution_time = fields.Char(string="Resolution Time")
    