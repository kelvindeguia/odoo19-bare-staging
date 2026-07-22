from odoo import api, fields, models


class ITNeoQuestion(models.Model):
    _name = "it.neo.question"
    _description = "NEO Survey Question"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class ITNeoSession(models.Model):
    _name = "it.neo.session"
    _description = "IT NEO Session"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "session_date desc"

    name = fields.Char(compute="_compute_name", store=True)
    period_id = fields.Many2one("it.dashboard.period", required=True, ondelete="cascade", index=True)
    session_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True, index=True)
    facilitator_id = fields.Many2one("res.users", tracking=True)
    new_hire_count = fields.Integer()
    response_count = fields.Integer(compute="_compute_scores", store=True)
    overall_score = fields.Float(compute="_compute_scores", store=True, digits=(4, 2))
    response_ids = fields.One2many("it.neo.response", "session_id")
    comments_summary = fields.Html()
    state = fields.Selection([("draft", "Draft"), ("confirmed", "Confirmed")], default="draft", tracking=True)

    @api.depends("session_date")
    def _compute_name(self):
        for rec in self:
            rec.name = f"NEO - {rec.session_date}" if rec.session_date else "NEO Session"

    @api.depends("response_ids.score")
    def _compute_scores(self):
        for rec in self:
            scores = rec.response_ids.mapped("score")
            rec.response_count = len(scores)
            rec.overall_score = sum(scores) / len(scores) if scores else 0.0

    def action_confirm(self):
        self.write({"state": "confirmed"})


class ITNeoResponse(models.Model):
    _name = "it.neo.response"
    _description = "NEO Survey Response"
    _order = "session_id, question_id"

    session_id = fields.Many2one("it.neo.session", required=True, ondelete="cascade", index=True)
    question_id = fields.Many2one("it.neo.question", required=True)
    score = fields.Float(required=True, digits=(4, 2))
    comment = fields.Text()
    respondent_reference = fields.Char(help="Optional anonymous or external response reference.")

    _score_range = models.Constraint("CHECK(score >= 0 AND score <= 5)", "The NEO score must be between 0 and 5.")
