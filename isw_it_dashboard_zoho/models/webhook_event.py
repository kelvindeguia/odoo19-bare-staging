from odoo import fields, models

class ITZohoWebhookEvent(models.Model):
    _name = "it.zoho.webhook.event"
    _description = "Zoho Desk Webhook Event"
    _order = "received_at desc"

    event_type = fields.Char(index=True)
    zoho_ticket_id = fields.Char(index=True)
    received_at = fields.Datetime(default=fields.Datetime.now, required=True)
    state = fields.Selection([("pending", "Pending"), ("processed", "Processed"), ("failed", "Failed")], default="pending", index=True)
    payload = fields.Text(required=True)
    error_message = fields.Text()

    def process_pending_events(self):
        for event in self.search([("state", "=", "pending")], limit=100):
            try:
                if event.zoho_ticket_id:
                    self.env["it.zoho.ticket"]._sync_single_ticket(event.zoho_ticket_id)
                event.state = "processed"
            except Exception as exc:
                event.write({"state": "failed", "error_message": str(exc)})
