from odoo import models, fields, api
from datetime import date
from odoo.exceptions import UserError

class ComplianceDashboard(models.Model):
    _name = 'it.compliance.dashboard'
    _description = 'IT Compliance Dashboard'
    _inherit = ['it.dashboard.weekly.mixin'] 

    name = fields.Char(default=lambda self: f"Compliance Dashboard Input - {date.today()}")

    _rec_name = 'name'

    active_compliances = fields.Integer(
        string="No. of Active Compliances",
        compute="_compute_active_compliances",
        store=True,
        readonly=True,
    )
    compliances = fields.Many2many(
        'it.active.compliance',
        'it_compliance_dashboard_compliance_rel',
        'dashboard_id',
        'compliance_id',
        string="Compliance",
    )
    compliance_stage_summary = fields.Text(compute="_compute_compliance_stage_summary")
    compliance_status = fields.Many2many(
        'it.active.compliance',
        'it_compliance_dashboard_status_rel',
        'dashboard_id',
        'compliance_id',
        string="Compliance Status",
    )
    compliance_progress = fields.Many2many(
        'it.active.compliance',
        'it_compliance_dashboard_progress_rel',
        'dashboard_id',
        'compliance_id',
        string="Compliance Progress",
    )
    pci_scanning_activities = fields.Selection([
        ('', 'Select Activity'),
        ('asv', 'ASV metrics'),
        ('iva', 'IVA metrics'),
        ('enpt', 'ENPT metrics'),
        ('intp', 'INTP metrics'),
    ])
    audit_findings = fields.Text(string="Audit Findings")
    it_risk_assessment_overview = fields.Text(string="IT Risk Assessment Overview")

    @api.depends("compliances")
    def _compute_active_compliances(self):
        for rec in self:
            rec.active_compliances = len(rec.compliances)

    @api.onchange("compliances")
    def _onchange_compliances(self):
        for rec in self:
            rec.compliance_status = rec.compliances
            rec.compliance_progress = rec.compliances

    @api.depends("compliances")
    def _compute_compliance_stage_summary(self):
        stage_map = dict(
            self.env["it.active.compliance"]
            ._fields["stage"]
            .selection
        )
        for rec in self:
            rec.compliance_stage_summary = "\n".join(
                f"{c.name}: {stage_map.get(c.stage,'-')}"
                for c in rec.compliances
            )

    @api.model
    def _sync_compliance_vals(self, vals):
        if "compliances" in vals:
            vals = dict(vals)
            vals["compliance_status"] = vals["compliances"]
            vals["compliance_progress"] = vals["compliances"]
        return vals

    def action_open_dashboard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "compliance_dashboard_live",  
            "target": "current",
            "context": {
                "active_id": self.id,
                "view_mode": "readonly",
            },
        }
    
    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._sync_compliance_vals(vals) for vals in vals_list]
        for vals in vals_list:
            summary_start = vals.get("summary_start")
            summary_end = vals.get("summary_end")

            if summary_start and summary_end:
                existing = self.search([
                    ("create_uid", "=", self.env.user.id),
                    ("summary_start", "=", summary_start),
                    ("summary_end", "=", summary_end),
                ], limit=1)

                if existing:
                    raise UserError(
                        "You have already submitted a dashboard entry for this "
                        "reporting week. Please edit your existing record instead."
                    )

        records = super().create(vals_list)
        records._sync_executive_summary()

        return records

    def write(self, vals):
        for rec in self:
            is_owner = rec.create_uid.id == self.env.user.id
            is_admin = self.env.user.has_group("base.group_system")

            if not (is_owner or is_admin):
                raise UserError(
                    "Only the original creator or an administrator can edit this record."
                )

        vals = self._sync_compliance_vals(vals)
        result = super().write(vals)
        self._sync_executive_summary()

        return result

    def unlink(self):
        for rec in self:
            is_owner = rec.create_uid.id == self.env.user.id
            is_admin = self.env.user.has_group("base.group_system")

            if not (is_owner or is_admin):
                raise UserError(
                    "Only the original creator or an administrator can delete this record."
                )

        return super().unlink()
    
    def _sync_executive_summary(self):
        for rec in self:
            self.env["it.dashboard.summary.history"].sync_week(
                rec.summary_start,
                rec.summary_end,
            )

class ActiveCompliance(models.Model):
    _name = 'it.active.compliance'
    _description = 'Active Compliances List'

    name = fields.Char(required=True)
    status = fields.Text(string="Compliance Status")
    progress = fields.Text(string="Compliance Progress")
    stage = fields.Selection([
        ('', 'Select Current Stage'),
        ('kickoff', 'Kickoff/Planning'),
        ('fieldwork', 'Fieldwork/Evidence Gathering'),
        ('audit', 'Audit'),
        ('reporting', 'Reporting'),
        ('certification', 'Certification'),
    ], string="Status", default='')
    
