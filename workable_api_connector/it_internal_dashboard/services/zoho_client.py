"""
zoho_client.py
--------------
Low-level HTTP client for Zoho APIs.
Knows nothing about Odoo models or field names.
Every other service uses this instead of calling requests directly.
"""
import requests
import logging
import time
from urllib.parse import urlsplit

_logger = logging.getLogger(__name__)

ZOHO_DESK_BASE = "https://desk.zoho.com/api/v1"
ZOHO_ANALYTICS_BASE = "https://analyticsapi.zoho.com/restapi/v2"


class ZohoClient:
    _SENSITIVE_PARAM_PARTS = (
        "authorization",
        "access_token",
        "refresh_token",
        "token",
        "cookie",
        "session",
        "csrf",
        "client_secret",
        "secret",
    )

    def __init__(self, access_token: str, org_id: str):
        if not access_token:
            raise ValueError(
                "Zoho access token is missing."
            )

        if not org_id:
            raise ValueError(
                "Zoho Desk org ID is missing. "
                "Check the active it.zoho.credentials record."
            )

        self._token = str(access_token).strip()
        self._org_id = str(org_id).strip()

        if not self._token:
            raise ValueError(
                "Zoho access token is empty."
            )

        if not self._org_id:
            raise ValueError(
                "Zoho Desk org ID is empty."
            )

        self._session = requests.Session()

        self._session.headers.update({
            "Authorization": f"Zoho-oauthtoken {self._token}",
            "orgId": self._org_id,
            "Content-Type": "application/json",
        })

    @classmethod
    def _sanitize_params(cls, params: dict = None) -> dict:
        safe_params = {}

        for key, value in (params or {}).items():
            normalized_key = str(key).lower()

            if any(part in normalized_key for part in cls._SENSITIVE_PARAM_PARTS):
                safe_params[key] = "<redacted>"
            else:
                safe_params[key] = value

        return safe_params

    @staticmethod
    def _endpoint_path(url: str) -> str:
        parsed = urlsplit(url)
        return parsed.path or url

    @staticmethod
    def _json_summary(payload: dict) -> dict:
        if not isinstance(payload, dict):
            return {
                "payload_type": type(payload).__name__,
            }

        summary = {
            "top_level_keys": sorted(payload.keys()),
        }

        data = payload.get("data")
        if isinstance(data, list):
            summary["data_count"] = len(data)
        elif isinstance(data, dict):
            summary["data_keys"] = sorted(data.keys())

        for key in ("count", "from", "limit", "moreRecords", "totalCount"):
            if key in payload:
                summary[key] = payload.get(key)

        return summary

    def get(self, url: str, params: dict = None) -> dict:
        start = time.monotonic()
        endpoint_path = self._endpoint_path(url)
        safe_params = self._sanitize_params(params)

        _logger.info(
            "Zoho API request: method=GET path=%s params=%s",
            endpoint_path,
            safe_params,
        )

        try:
            response = self._session.get(url, params=params, timeout=20)
            duration_ms = int((time.monotonic() - start) * 1000)

            _logger.info(
                "Zoho API response: method=GET path=%s status=%s duration_ms=%s",
                endpoint_path,
                response.status_code,
                duration_ms,
            )

            if response.status_code == 429:
                # Zoho rate limit: wait the time they tell you to wait
                retry_after = int(
                    response.headers.get("Retry-After", 10)
                )
                _logger.warning(
                    "Zoho rate limit hit. Waiting %s seconds.", retry_after
                )
                time.sleep(retry_after)
                response = self._session.get(url, params=params, timeout=20)
                duration_ms = int((time.monotonic() - start) * 1000)
                _logger.info(
                    "Zoho API retry response: method=GET path=%s status=%s duration_ms=%s",
                    endpoint_path,
                    response.status_code,
                    duration_ms,
                )

            response.raise_for_status()
            data = response.json()

            _logger.info(
                "Zoho API response summary: method=GET path=%s summary=%s",
                endpoint_path,
                self._json_summary(data),
            )

            return data

        except requests.exceptions.Timeout:
            raise ConnectionError(
                f"Zoho API timed out: {url}"
            )
        except requests.exceptions.ConnectionError as exc:
            raise ConnectionError(
                f"Cannot reach Zoho: {exc}"
            )
        except requests.exceptions.HTTPError as exc:
            raise ValueError(
                f"Zoho returned HTTP {response.status_code}: "
                f"{response.text[:500]}"
            ) from exc

    def post(self, url: str, payload: dict) -> dict:
        start = time.monotonic()
        endpoint_path = self._endpoint_path(url)

        _logger.info(
            "Zoho API request: method=POST path=%s payload_keys=%s",
            endpoint_path,
            sorted((payload or {}).keys()),
        )

        try:
            response = self._session.post(url, json=payload, timeout=20)
            duration_ms = int((time.monotonic() - start) * 1000)
            _logger.info(
                "Zoho API response: method=POST path=%s status=%s duration_ms=%s",
                endpoint_path,
                response.status_code,
                duration_ms,
            )
            response.raise_for_status()
            data = response.json()
            _logger.info(
                "Zoho API response summary: method=POST path=%s summary=%s",
                endpoint_path,
                self._json_summary(data),
            )
            return data
        except requests.exceptions.RequestException as exc:
            raise ConnectionError(f"Zoho POST failed: {exc}") from exc
