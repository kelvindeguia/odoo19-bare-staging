# -*- coding: utf-8 -*-

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class WorkableOutboundSyncMixin(models.AbstractModel):
    _name = "workable.outbound.sync.mixin"
    _description = "Workable Outbound Sync Mixin"

    def _should_skip_workable_outbound_sync(self):
        if self.env.context.get("skip_workable_outbound_sync"):
            return True
        enabled = self.env["ir.config_parameter"].sudo().get_param("workable.outbound_sync_enabled")
        return enabled not in ("1", "True", "true", True)

    def _queue_workable_outbound_update(self, operation="update", payload=None):
        # Placeholder for phase 2 outbound sync.
        # Keep this as a safe extension point instead of pushing automatically from every write().
        if self._should_skip_workable_outbound_sync():
            return False
        _logger.info("Outbound Workable sync requested: model=%s ids=%s operation=%s", self._name, self.ids, operation)
        return True
