# -*- coding: utf-8 -*-

import logging
import time

import requests

from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

WORKABLE_API_BASE = "https://{subdomain}.workable.com/spi/v3"


class WorkableApiMixin(models.AbstractModel):
    _name = "workable.api.mixin"
    _description = "Workable API Mixin"

    def _get_workable_credentials(self):
        ICP = self.env["ir.config_parameter"].sudo()
        token = ICP.get_param("workable.api_token")
        subdomain = ICP.get_param("workable.subdomain")

        if not token or not subdomain:
            raise UserError(_(
                "Workable API Token or Subdomain is not configured. "
                "Go to Settings > General Settings > Workable Integration."
            ))

        return token.strip(), subdomain.strip().replace("https://", "").replace("http://", "").replace(".workable.com", "").strip("/")

    def _workable_base_url(self):
        _token, subdomain = self._get_workable_credentials()
        return WORKABLE_API_BASE.format(subdomain=subdomain)

    def _workable_headers(self):
        token, _subdomain = self._get_workable_credentials()
        return {
            "Authorization": "Bearer %s" % token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _workable_request(self, method, path, params=None, json_payload=None, timeout=30, max_retries=5):
        base_url = self._workable_base_url()
        url = path if str(path).startswith("http") else "%s%s" % (base_url, path)
        headers = self._workable_headers()
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_payload,
                    timeout=timeout,
                )

                if response.status_code == 429:
                    wait = int(response.headers.get("Retry-After", retry_delay))
                    _logger.warning(
                        "Workable rate limit hit. Waiting %s seconds. attempt=%s/%s path=%s",
                        wait, attempt + 1, max_retries, path,
                    )
                    time.sleep(wait)
                    retry_delay *= 2
                    continue

                if response.status_code >= 400:
                    raise UserError(_("Workable API error %(status)s on %(path)s: %(body)s") % {
                        "status": response.status_code,
                        "path": path,
                        "body": response.text[:1000],
                    })

                if not response.text:
                    return {}

                try:
                    return response.json()
                except Exception:
                    raise UserError(_("Invalid JSON response from Workable on %s: %s") % (path, response.text[:1000]))

            except requests.exceptions.RequestException as exc:
                if attempt == max_retries - 1:
                    raise UserError(_("Failed to connect to Workable: %s") % exc)
                time.sleep(retry_delay)
                retry_delay *= 2

        raise UserError(_("Max retries exceeded for Workable request: %s") % path)
