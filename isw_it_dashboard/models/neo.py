from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


MONTH_SELECTION = [
    ("1", "January"),
    ("2", "February"),
    ("3", "March"),
    ("4", "April"),
    ("5", "May"),
    ("6", "June"),
    ("7", "July"),
    ("8", "August"),
    ("9", "September"),
    ("10", "October"),
    ("11", "November"),
    ("12", "December"),
]


class ITNeoQuestion(models.Model):
    _name = "it.neo.question"
    _description = "IT NEO Satisfaction Question"
    _order = "sequence, id"

    name = fields.Char(string="Question", required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class ITNeoSession(models.Model):
    _name = "it.neo.session"
    _description = "IT NEO Satisfaction Entry"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "session_date desc, id desc"
    _rec_name = "name"
    _check_company_auto = True

    name = fields.Char(compute="_compute_name", store=True)
    session_date = fields.Date(
        string="NEO Date",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        index=True,
    )
    month = fields.Selection(
        selection=MONTH_SELECTION,
        compute="_compute_period_fields",
        store=True,
        index=True,
    )
    year = fields.Integer(
        compute="_compute_period_fields",
        store=True,
        index=True,
    )
    period_date = fields.Date(
        string="Reporting Month",
        compute="_compute_period_fields",
        store=True,
        index=True,
        help="First day of the reporting month for QuickSight filtering.",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
        index=True,
    )
    target_id = fields.Many2one(
        "it.helpdesk.monthly.target",
        string="Monthly Target",
        check_company=True,
        tracking=True,
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
    )
    neo_target = fields.Float(
        string="NEO Target",
        related="target_id.neo_target",
        store=True,
        readonly=True,
        digits=(16, 2),
    )
    facilitator_id = fields.Many2one(
        "res.users",
        string="Facilitator",
        tracking=True,
    )
    attendee_count = fields.Integer(
        string="New Hire Attendees",
        tracking=True,
    )
    respondent_count = fields.Integer(
        string="Survey Respondents",
        tracking=True,
    )
    response_count = fields.Integer(
        string="Scored Questions",
        compute="_compute_scores",
        store=True,
    )
    overall_score = fields.Float(
        string="Overall Score",
        compute="_compute_scores",
        store=True,
        digits=(16, 2),
        tracking=True,
    )
    score_line_ids = fields.One2many(
        "it.neo.response",
        "session_id",
        string="Question Scores",
        copy=True,
    )
    comment_ids = fields.One2many(
        "it.neo.comment",
        "session_id",
        string="Comments and Recommendations",
        copy=True,
    )
    general_notes = fields.Text(string="General Notes", tracking=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("locked", "Locked"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )

    _unique_session_date_company = models.Constraint(
        "UNIQUE(session_date, company_id)",
        "Only one IT NEO satisfaction entry is allowed per date and company.",
    )

    @api.depends("session_date")
    def _compute_name(self):
        for rec in self:
            rec.name = (
                f"IT NEO Satisfaction - {fields.Date.to_string(rec.session_date)}"
                if rec.session_date
                else "New IT NEO Satisfaction Entry"
            )

    @api.depends("session_date")
    def _compute_period_fields(self):
        for rec in self:
            if rec.session_date:
                session_date = fields.Date.to_date(rec.session_date)
                rec.month = str(session_date.month)
                rec.year = session_date.year
                rec.period_date = date(session_date.year, session_date.month, 1)
            else:
                rec.month = False
                rec.year = 0
                rec.period_date = False

    @api.depends("score_line_ids.score")
    def _compute_scores(self):
        for rec in self:
            scores = rec.score_line_ids.mapped("score")
            rec.response_count = len(scores)
            rec.overall_score = round(sum(scores) / len(scores), 2) if scores else 0.0

    @api.onchange("session_date", "company_id")
    def _onchange_session_period(self):
        for rec in self:
            rec.target_id = False
            if not rec.session_date or not rec.company_id:
                continue
            session_date = fields.Date.to_date(rec.session_date)
            target = self.env["it.helpdesk.monthly.target"].search(
                [
                    ("month", "=", str(session_date.month)),
                    ("year", "=", session_date.year),
                    ("company_id", "=", rec.company_id.id),
                    ("active", "=", True),
                ],
                limit=1,
            )
            rec.target_id = target

    @api.constrains("target_id", "session_date", "company_id")
    def _check_target_period(self):
        for rec in self:
            if not rec.target_id or not rec.session_date:
                continue
            session_date = fields.Date.to_date(rec.session_date)
            if (
                rec.target_id.month != str(session_date.month)
                or rec.target_id.year != session_date.year
                or rec.target_id.company_id != rec.company_id
            ):
                raise ValidationError(
                    _("The selected monthly target does not match the NEO date and company.")
                )

    @api.constrains("attendee_count", "respondent_count")
    def _check_counts(self):
        for rec in self:
            if rec.attendee_count < 0 or rec.respondent_count < 0:
                raise ValidationError(_("Attendee and respondent counts cannot be negative."))
            if rec.attendee_count and rec.respondent_count > rec.attendee_count:
                raise ValidationError(
                    _("Survey respondents cannot exceed the number of attendees.")
                )

    def action_confirm(self):
        for rec in self:
            if not rec.score_line_ids:
                raise UserError(_("Add at least one question score before confirming."))
            rec.state = "confirmed"

    def action_lock(self):
        self.write({"state": "locked"})

    def action_reset_to_draft(self):
        self.write({"state": "draft"})


class ITNeoResponse(models.Model):
    _name = "it.neo.response"
    _description = "IT NEO Question Score"
    _order = "session_id, sequence, id"

    session_id = fields.Many2one(
        "it.neo.session",
        required=True,
        ondelete="cascade",
        index=True,
    )
    question_id = fields.Many2one(
        "it.neo.question",
        required=True,
        domain="[('active', '=', True)]",
    )
    sequence = fields.Integer(related="question_id.sequence", store=True)
    score = fields.Float(required=True, digits=(16, 2))
    notes = fields.Char(string="Score Notes")

    _score_range = models.Constraint(
        "CHECK(score >= 0 AND score <= 5)",
        "The NEO score must be between 0 and 5.",
    )
    _unique_question_session = models.Constraint(
        "UNIQUE(session_id, question_id)",
        "Each NEO question can only be entered once per session.",
    )


class ITNeoComment(models.Model):
    _name = "it.neo.comment"
    _description = "IT NEO Comment or Recommendation"
    _order = "session_id, sequence, id"

    session_id = fields.Many2one(
        "it.neo.session",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    comment = fields.Text(required=True)
    category = fields.Selection(
        [
            ("comment", "Comment"),
            ("recommendation", "Recommendation"),
            ("positive", "Positive Feedback"),
            ("improvement", "Improvement Opportunity"),
        ],
        default="comment",
        required=True,
    )
