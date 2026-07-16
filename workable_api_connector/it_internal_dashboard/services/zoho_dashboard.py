"""
zoho_dashboard.py
"""
import logging
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9 fallback
    ZoneInfo = None
from .zoho_client import ZohoClient, ZOHO_DESK_BASE

_logger = logging.getLogger(__name__)

CHANNEL_GROUPS = {
    "web": {"WEBFORM", "WEB"},
    "email": {"EMAIL"},
    "phone": {"PHONE", "PHONECALL"},
}


class ZohoDashboardService:

    def __init__(self, access_token: str, org_id: str, workspace_id: str = None):
        self._client = ZohoClient(access_token, org_id)
        self._org_id = org_id
        self._workspace_id = workspace_id
        self._it_department_id = None
        self._zoho_timezone_name = None

    # Helper: Fetch Department ID dynamically
    def get_it_department_id(
        self,
        department_name: str,
    ):
        if self._it_department_id:
            return self._it_department_id

        if not department_name:
            raise ValueError(
                "Zoho Desk department name is required."
            )

        url = f"{ZOHO_DESK_BASE}/departments"

        data = self._client.get(
            url,
            params={
                "isEnabled": "true",
            },
        )

        departments = data.get("data", [])

        _logger.info(
            "Zoho Desk departments returned: %s",
            len(departments),
        )

        target_name = (
            str(department_name)
            .strip()
            .casefold()
        )

        for department in departments:
            department_id = department.get("id")
            department_name_value = (
                department.get("name") or ""
            )

            _logger.info(
                "Zoho Desk department candidate: "
                "id=%s name=%r",
                department_id,
                department_name_value,
            )

            normalized_name = (
                str(department_name_value)
                .strip()
                .casefold()
            )

            if normalized_name == target_name:
                self._it_department_id = str(
                    department_id
                )

                _logger.info(
                    "Matched Zoho Desk department: "
                    "id=%s name=%r",
                    self._it_department_id,
                    department_name_value,
                )

                return self._it_department_id

        _logger.warning(
            "Zoho Desk department not found: %r",
            department_name,
        )

        return None

    def _find_timezone_value(self, value):
        timezone_keys = {
            "timezone",
            "timeZone",
            "time_zone",
            "orgTimeZone",
            "portalTimeZone",
            "timeZoneName",
        }

        if isinstance(value, dict):
            for key, item in value.items():
                if key in timezone_keys and item:
                    return str(item).strip()

            for item in value.values():
                found = self._find_timezone_value(item)
                if found:
                    return found

        if isinstance(value, list):
            for item in value:
                found = self._find_timezone_value(item)
                if found:
                    return found

        return None

    @staticmethod
    def _is_valid_timezone_name(timezone_name):
        if not timezone_name or not ZoneInfo:
            return False

        try:
            ZoneInfo(str(timezone_name).strip())
            return True
        except Exception:
            return False

    def get_zoho_timezone_name(self):
        if self._zoho_timezone_name:
            return self._zoho_timezone_name

        url = f"{ZOHO_DESK_BASE}/organizations"
        data = self._client.get(url)

        timezone_name = self._find_timezone_value(data)

        if self._is_valid_timezone_name(timezone_name):
            self._zoho_timezone_name = timezone_name
            _logger.info(
                "Resolved Zoho organization timezone: %s",
                timezone_name,
            )
            return timezone_name

        agent_timezone_name = self._get_agent_timezone_name()

        if agent_timezone_name:
            self._zoho_timezone_name = agent_timezone_name
            _logger.info(
                "Resolved Zoho reporting timezone from agent metadata: %s",
                agent_timezone_name,
            )
            return agent_timezone_name

        raise ValueError(
            "Unable to resolve a valid Zoho reporting timezone from "
            "organization or agent metadata. Configure an explicit "
            "reporting timezone before running Last 24 Hours KPI sync."
        )

    def _get_agent_timezone_name(self):
        url = f"{ZOHO_DESK_BASE}/agents"

        data = self._client.get(
            url,
            params={
                "from": 1,
                "limit": 10,
            },
        )

        timezone_counts = {}

        for agent in data.get("data", []):
            timezone_name = (
                agent.get("timeZone")
                or agent.get("timezone")
                or agent.get("time_zone")
            )

            if not self._is_valid_timezone_name(timezone_name):
                continue

            timezone_name = str(timezone_name).strip()
            timezone_counts[timezone_name] = (
                timezone_counts.get(timezone_name, 0) + 1
            )

        if not timezone_counts:
            return None

        if len(timezone_counts) > 1:
            _logger.warning(
                "Multiple Zoho agent timezones observed: %s. "
                "Using the most common timezone for reporting diagnostics.",
                timezone_counts,
            )

        return sorted(
            timezone_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[0][0]

    def _timezone(self):
        timezone_name = self.get_zoho_timezone_name()

        if ZoneInfo:
            return ZoneInfo(timezone_name)

        raise ValueError(
            "Python zoneinfo is unavailable; cannot build an aware "
            "Zoho reporting window."
        )

    def resolve_reporting_window(self, period_key="last_24_hours"):
        if period_key != "last_24_hours":
            raise ValueError(
                "Unsupported Zoho reporting period: %s" % period_key
            )

        tz = self._timezone()
        timezone_name = self.get_zoho_timezone_name()
        window_end = datetime.now(tz)
        window_start = window_end - timedelta(hours=24)

        window = {
            "period_key": period_key,
            "window_start": window_start,
            "window_end": window_end,
            "timezone": timezone_name,
        }

        _logger.info(
            "Resolved Zoho reporting window: period_key=%s window_start=%s "
            "window_end=%s timezone=%s",
            period_key,
            window_start.isoformat(),
            window_end.isoformat(),
            timezone_name,
        )

        return window

    @staticmethod
    def _legacy_date_bounds_utc(start_date, end_date):
        return (
            datetime.combine(
                start_date,
                datetime.min.time(),
            ).replace(tzinfo=timezone.utc),
            datetime.combine(
                end_date,
                datetime.max.time(),
            ).replace(tzinfo=timezone.utc),
        )
    
    # GET /api/v1/customerHappiness
    def get_customer_happiness(
        self,
        start_date,
        end_date,
        department_id: str = None,
        page_limit: int = 50,
        max_pages: int = 20,
    ) -> dict:
        """
        Return customer happiness rating counts for the requested reporting
        window.

        Zoho Desk returns /customerHappiness oldest-first unless sortBy is
        explicitly supplied. Request newest-first so pagination can stop as
        soon as records are older than the reporting window.
        """
        url = f"{ZOHO_DESK_BASE}/customerHappiness"

        start_dt, end_dt = self._legacy_date_bounds_utc(
            start_date,
            end_date,
        )

        counts = {
            "GOOD": 0,
            "OK": 0,
            "BAD": 0,
        }

        for page in range(max_pages):
            offset = page * page_limit

            params = {
                "from": offset,
                "limit": page_limit,
                "sortBy": "-ratedTime",
            }

            if department_id:
                params["department"] = department_id

            data = self._client.get(
                url,
                params,
            )

            records = data.get("data", [])

            if not records:
                break

            _logger.info(
                "Zoho customer happiness page: "
                "offset=%s count=%s",
                offset,
                len(records),
            )

            stop_paging = False

            for record in records:
                rated_dt = self._parse_zoho_dt(
                    record.get("ratedTime")
                )

                if not rated_dt:
                    _logger.warning(
                        "Skipping Zoho happiness record %s "
                        "with invalid ratedTime %r",
                        record.get("id"),
                        record.get("ratedTime"),
                    )
                    continue

                if rated_dt < start_dt:
                    stop_paging = True
                    continue

                if rated_dt > end_dt:
                    continue

                rating = str(
                    record.get("rating") or ""
                ).strip().upper()

                if rating in counts:
                    counts[rating] += 1
                else:
                    _logger.warning(
                        "Unknown Zoho happiness rating %r "
                        "for record %s",
                        rating,
                        record.get("id"),
                    )

            if stop_paging:
                break

            if len(records) < page_limit:
                break

        result = {
            "good_rating": counts["GOOD"],
            "okay_rating": counts["OK"],
            "bad_rating": counts["BAD"],
        }

        _logger.info(
            "Zoho weekly customer happiness: "
            "department=%s range=%s to %s result=%s",
            department_id,
            start_date,
            end_date,
            result,
        )

        return result

    def get_customer_happiness_for_window(
        self,
        window,
        department_id: str = None,
        page_limit: int = 50,
        max_pages: int = 20,
    ) -> dict:
        url = f"{ZOHO_DESK_BASE}/customerHappiness"
        window_start = window["window_start"]
        window_end = window["window_end"]

        raw_ratings = {}

        for page in range(max_pages):
            offset = page * page_limit

            params = {
                "from": offset,
                "limit": page_limit,
                "sortBy": "-ratedTime",
            }

            if department_id:
                params["department"] = department_id

            data = self._client.get(
                url,
                params,
            )

            records = data.get("data", [])

            if not records:
                break

            stop_paging = False

            for record in records:
                rated_dt = self._parse_zoho_dt(
                    record.get("ratedTime")
                )

                if not rated_dt:
                    continue

                rated_dt = rated_dt.astimezone(
                    window_start.tzinfo
                )

                if rated_dt < window_start:
                    stop_paging = True
                    continue

                if rated_dt > window_end:
                    continue

                rating = str(
                    record.get("rating") or "UNKNOWN"
                ).strip().upper() or "UNKNOWN"

                raw_ratings[rating] = (
                    raw_ratings.get(rating, 0) + 1
                )

            if stop_paging:
                break

            if len(records) < page_limit:
                break

        result = {
            "raw_rating_counts": raw_ratings,
            "good_rating": raw_ratings.get("GOOD", 0),
            "okay_rating": raw_ratings.get("OK", 0),
            "bad_rating": raw_ratings.get("BAD", 0),
        }

        _logger.info(
            "Zoho Last 24 Hours happiness diagnostic: department=%s "
            "period_key=%s window_start=%s window_end=%s timezone=%s "
            "raw_ratings=%s mapped_good=%s mapped_okay=%s mapped_bad=%s",
            department_id,
            window["period_key"],
            window_start.isoformat(),
            window_end.isoformat(),
            window["timezone"],
            raw_ratings,
            result["good_rating"],
            result["okay_rating"],
            result["bad_rating"],
        )

        return result
    
    # GET /api/v1/dashboards/createdTickets
    def get_created_tickets_count(
        self,
        start_date,
        end_date,
        department_id=None,
        page_limit=50,
        max_pages=100,
    ) -> int:
        tickets = self._get_tickets_in_range(
            start_date=start_date,
            end_date=end_date,
            department_id=department_id,
            fields=[
                "id",
                "createdTime",
            ],
            page_limit=page_limit,
            max_pages=max_pages,
        )

        ticket_count = len(tickets)

        _logger.info(
            "Zoho ticket count: %s "
            "department=%s range=%s to %s",
            ticket_count,
            department_id,
            start_date,
            end_date,
        )

        return ticket_count

    def _get_tickets_in_range(
        self,
        start_date,
        end_date,
        department_id=None,
        fields=None,
        page_limit=50,
        max_pages=100,
    ) -> list:
        """
        Return unique Zoho Desk tickets created inside the requested
        reporting window.

        The ticket list is sorted newest-first. Pagination stops once
        tickets older than the reporting window are reached.

        This method is the canonical ticket population loader for all
        weekly dashboard metrics.
        """

        url = f"{ZOHO_DESK_BASE}/tickets"

        requested_fields = fields or [
            "id",
            "createdTime",
            "customerResponseTime",
            "closedTime",
            "modifiedTime",
            "channel",
            "status",
        ]

        fields_param = ",".join(requested_fields)

        start_dt, end_dt = self._legacy_date_bounds_utc(
            start_date,
            end_date,
        )

        tickets_in_range = []
        seen_ticket_ids = set()

        for page in range(max_pages):
            params = {
                "from": (page * page_limit) + 1,
                "limit": page_limit,
                "sortBy": "-createdTime",
                "fields": fields_param,
            }

            if department_id:
                params["departmentId"] = department_id

            data = self._client.get(
                url,
                params,
            )

            tickets = data.get("data", [])

            if not tickets:
                break

            reached_older_ticket = False

            for ticket in tickets:
                created_dt = self._parse_zoho_dt(
                    ticket.get("createdTime")
                )

                if not created_dt:
                    continue

                if created_dt < start_dt:
                    reached_older_ticket = True
                    continue

                if created_dt > end_dt:
                    continue

                ticket_id = str(
                    ticket.get("id") or ""
                ).strip()

                if not ticket_id:
                    continue

                if ticket_id in seen_ticket_ids:
                    continue

                seen_ticket_ids.add(ticket_id)
                tickets_in_range.append(ticket)

            if reached_older_ticket:
                break

            if len(tickets) < page_limit:
                break

        _logger.info(
            "Zoho ticket population: "
            "department=%s range=%s to %s "
            "tickets=%s unique_ids=%s",
            department_id,
            start_date,
            end_date,
            len(tickets_in_range),
            len(seen_ticket_ids),
        )

        return tickets_in_range
    
    # GET /api/v1/channels + GET /api/v1/ticketsCount
    def get_channel_list(self) -> list:
        url = f"{ZOHO_DESK_BASE}/channels"
        data = self._client.get(url)
        return data.get("data", [])

    def get_channel_breakdown(
        self,
        start_date,
        end_date,
        department_id=None,
    ) -> dict:
        tickets = self._get_tickets_in_range(
            start_date=start_date,
            end_date=end_date,
            department_id=department_id,
            fields=[
                "id",
                "createdTime",
                "channel",
            ],
        )

        result = {
            "web": 0,
            "email": 0,
            "phone": 0,
        }

        unknown_channels = {}

        for ticket in tickets:
            channel = str(
                ticket.get("channel") or ""
            ).strip().upper()

            matched = False

            for group, codes in CHANNEL_GROUPS.items():
                normalized_codes = {
                    str(code).strip().upper()
                    for code in codes
                }

                if channel in normalized_codes:
                    result[group] += 1
                    matched = True
                    break

            if not matched:
                unknown_channels[channel] = (
                    unknown_channels.get(channel, 0) + 1
                )

        _logger.info(
            "Zoho weekly channel breakdown: "
            "department=%s range=%s to %s "
            "result=%s unknown=%s total=%s",
            department_id,
            start_date,
            end_date,
            result,
            unknown_channels,
            sum(result.values()),
        )

        return result

    # GET /api/v1/ticketsCountByFieldValues (status breakdown)
    def get_ticket_counts(
        self,
        start_date,
        end_date,
        department_id=None,
    ) -> dict:
        tickets = self._get_tickets_in_range(
            start_date=start_date,
            end_date=end_date,
            department_id=department_id,
            fields=[
                "id",
                "createdTime",
                "status",
            ],
        )

        status_map = {}

        for ticket in tickets:
            status = str(
                ticket.get("status") or ""
            ).strip().lower()

            status_map[status] = (
                status_map.get(status, 0) + 1
            )

        new_tickets = status_map.get(
            "open",
            0,
        )

        on_hold_tickets = status_map.get(
            "on hold",
            0,
        )

        closed_tickets = (
            status_map.get("closed", 0)
            + status_map.get("resolved", 0)
        )

        backlog = (
            status_map.get("open", 0)
            + status_map.get("on hold", 0)
            + status_map.get(
                "waiting for end-user",
                0,
            )
            + status_map.get(
                "waiting for 3rd party",
                0,
            )
        )

        result = {
            "new_tickets": new_tickets,
            "on_hold_tickets": on_hold_tickets,
            "closed_tickets": closed_tickets,
            "backlog": backlog,
        }

        _logger.info(
            "Zoho weekly ticket status breakdown: "
            "department=%s range=%s to %s "
            "status_map=%s result=%s ticket_total=%s",
            department_id,
            start_date,
            end_date,
            status_map,
            result,
            len(tickets),
        )

        return result

    # GET /api/v1/tickets — used for first-response / resolution durations.
    # Chosen over GET /tickets/{id} because we need to average across
    # every ticket in the reporting window, not fetch one at a time.
    def get_ticket_time_metrics(
        self,
        start_date,
        end_date,
        department_id=None,
        page_limit=50,
        max_pages=100,
    ) -> dict:
        tickets = self._get_tickets_in_range(
            start_date=start_date,
            end_date=end_date,
            department_id=department_id,
            fields=[
                "id",
                "createdTime",
                "customerResponseTime",
                "closedTime",
                "modifiedTime",
                "status",
            ],
            page_limit=page_limit,
            max_pages=max_pages,
        )

        first_response_deltas = []
        resolution_deltas = []

        for ticket in tickets:
            created = self._parse_zoho_dt(
                ticket.get("createdTime")
            )

            if not created:
                continue

            responded = self._parse_zoho_dt(
                ticket.get("customerResponseTime")
            )

            if responded and responded >= created:
                first_response_deltas.append(
                    (responded - created).total_seconds()
                )

            status = str(
                ticket.get("status") or ""
            ).strip().lower()

            closed = self._parse_zoho_dt(
                ticket.get("closedTime")
            )

            if (
                not closed
                and status in {"closed", "resolved"}
            ):
                closed = self._parse_zoho_dt(
                    ticket.get("modifiedTime")
                )

            if closed and closed >= created:
                resolution_deltas.append(
                    (closed - created).total_seconds()
                )

        result = {
            "first_repsponse_time": (
                self._format_avg_duration(
                    first_response_deltas
                )
            ),
            "response_time": (
                self._format_avg_duration(
                    first_response_deltas
                )
            ),
            "resolution_time": (
                self._format_avg_duration(
                    resolution_deltas
                )
            ),
        }

        _logger.info(
            "Zoho weekly ticket time metrics: "
            "department=%s range=%s to %s "
            "tickets=%s first_response_samples=%s "
            "resolution_samples=%s result=%s",
            department_id,
            start_date,
            end_date,
            len(tickets),
            len(first_response_deltas),
            len(resolution_deltas),
            result,
        )

        return result

    @staticmethod
    def _parse_zoho_dt(value):
        if not value:
            return None
        normalized = str(value).strip()
        if normalized.endswith("Z"):
            normalized = "%s+00:00" % normalized[:-1]

        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
                try:
                    parsed = datetime.strptime(normalized, fmt)
                    break
                except ValueError:
                    parsed = None

            if not parsed:
                return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed

    def get_created_tickets_for_window(
        self,
        window,
        department_id=None,
        page_limit=50,
        max_pages=100,
    ):
        url = f"{ZOHO_DESK_BASE}/tickets"
        window_start = window["window_start"]
        window_end = window["window_end"]
        tickets_in_window = []
        seen_ticket_ids = set()

        fields_param = ",".join([
            "id",
            "createdTime",
            "channel",
            "status",
        ])

        for page in range(max_pages):
            params = {
                "from": (page * page_limit) + 1,
                "limit": page_limit,
                "sortBy": "-createdTime",
                "fields": fields_param,
            }

            if department_id:
                params["departmentId"] = department_id

            data = self._client.get(
                url,
                params,
            )

            tickets = data.get("data", [])

            if not tickets:
                break

            reached_older_ticket = False

            for ticket in tickets:
                created_dt = self._parse_zoho_dt(
                    ticket.get("createdTime")
                )

                if not created_dt:
                    continue

                created_dt = created_dt.astimezone(
                    window_start.tzinfo
                )

                if created_dt < window_start:
                    reached_older_ticket = True
                    continue

                if created_dt > window_end:
                    continue

                ticket_id = str(
                    ticket.get("id") or ""
                ).strip()

                if not ticket_id or ticket_id in seen_ticket_ids:
                    continue

                seen_ticket_ids.add(ticket_id)
                tickets_in_window.append(ticket)

            if reached_older_ticket:
                break

            if len(tickets) < page_limit:
                break

        _logger.info(
            "Zoho created-ticket diagnostic population: department=%s "
            "period_key=%s window_start=%s window_end=%s timezone=%s "
            "created_ticket_count=%s",
            department_id,
            window["period_key"],
            window_start.isoformat(),
            window_end.isoformat(),
            window["timezone"],
            len(tickets_in_window),
        )

        return tickets_in_window

    def summarize_channels(self, tickets):
        raw_channels = {}
        mapped = {
            "web": 0,
            "email": 0,
            "phone": 0,
        }

        for ticket in tickets:
            channel = str(
                ticket.get("channel") or "UNKNOWN"
            ).strip().upper() or "UNKNOWN"

            raw_channels[channel] = (
                raw_channels.get(channel, 0) + 1
            )

            for group, codes in CHANNEL_GROUPS.items():
                normalized_codes = {
                    str(code).strip().upper()
                    for code in codes
                }

                if channel in normalized_codes:
                    mapped[group] += 1
                    break

        return {
            "raw_channels": raw_channels,
            "mapped": mapped,
            "mapped_total": sum(mapped.values()),
            "raw_total": sum(raw_channels.values()),
        }

    def diagnose_last_24_hours_created_tickets(self):
        department_id = self.get_it_department_id(
            "Information Technology"
        )

        if not department_id:
            raise ValueError(
                "Zoho Desk department 'Information Technology' was not found."
            )

        window = self.resolve_reporting_window(
            "last_24_hours"
        )

        tickets = self.get_created_tickets_for_window(
            window,
            department_id=department_id,
        )

        status_map = {}

        for ticket in tickets:
            status = str(
                ticket.get("status") or ""
            ).strip().lower()

            status_map[status] = (
                status_map.get(status, 0) + 1
            )

        channel_summary = self.summarize_channels(tickets)

        result = {
            "department_name": "Information Technology",
            "department_id": department_id,
            "period_key": window["period_key"],
            "timezone": window["timezone"],
            "window_start": window["window_start"].isoformat(),
            "window_end": window["window_end"].isoformat(),
            "created_ticket_count": len(tickets),
            "old_open_status_new_ticket_count": status_map.get("open", 0),
            "status_counts": status_map,
            "raw_channel_counts": channel_summary["raw_channels"],
            "mapped_web_count": channel_summary["mapped"]["web"],
            "mapped_email_count": channel_summary["mapped"]["email"],
            "mapped_phone_count": channel_summary["mapped"]["phone"],
            "mapped_channel_total": channel_summary["mapped_total"],
            "raw_channel_total": channel_summary["raw_total"],
        }

        _logger.info(
            "Zoho Last 24 Hours created-ticket diagnostic: %s",
            result,
        )

        return result

    def get_last_24_hours_created_ticket_snapshot(self):
        """
        Return the validated Last 24 Hours created-ticket snapshot.

        Zoho Overview's New Tickets card is a created-ticket population
        for the selected reporting period. For this phase, ticket_count
        and new_tickets intentionally represent the same canonical
        Last 24 Hours created-ticket population. Channels are derived
        from that exact same ticket list and raw channel counts are kept
        for diagnostics rather than forced into Web/Email/Phone.
        """
        department_id = self.get_it_department_id(
            "Information Technology"
        )

        if not department_id:
            raise ValueError(
                "Zoho Desk department 'Information Technology' was not found."
            )

        window = self.resolve_reporting_window(
            "last_24_hours"
        )

        tickets = self.get_created_tickets_for_window(
            window,
            department_id=department_id,
        )

        channel_summary = self.summarize_channels(tickets)
        created_ticket_count = len(tickets)

        result = {
            "period_key": window["period_key"],
            "window_start": window["window_start"],
            "window_end": window["window_end"],
            "timezone": window["timezone"],
            "department_id": department_id,
            "ticket_count": created_ticket_count,
            "new_tickets": created_ticket_count,
            "tickets_from_web": channel_summary["mapped"]["web"],
            "tickets_from_email": channel_summary["mapped"]["email"],
            "tickets_from_phone": channel_summary["mapped"]["phone"],
            "raw_channel_counts": channel_summary["raw_channels"],
        }

        _logger.info(
            "Zoho Last 24 Hours created-ticket production snapshot: "
            "department=%s period_key=%s window_start=%s window_end=%s "
            "timezone=%s ticket_count=%s new_tickets=%s raw_channels=%s "
            "mapped_web=%s mapped_email=%s mapped_phone=%s",
            department_id,
            result["period_key"],
            result["window_start"].isoformat(),
            result["window_end"].isoformat(),
            result["timezone"],
            result["ticket_count"],
            result["new_tickets"],
            result["raw_channel_counts"],
            result["tickets_from_web"],
            result["tickets_from_email"],
            result["tickets_from_phone"],
        )

        return result

    @staticmethod
    def _flatten_metric_keys(value, prefix=""):
        keys = []

        if isinstance(value, dict):
            for key, item in value.items():
                name = "%s.%s" % (prefix, key) if prefix else str(key)
                keys.append(name)
                keys.extend(
                    ZohoDashboardService._flatten_metric_keys(
                        item,
                        name,
                    )
                )
        elif isinstance(value, list):
            for index, item in enumerate(value[:3]):
                name = "%s[%s]" % (prefix, index)
                keys.extend(
                    ZohoDashboardService._flatten_metric_keys(
                        item,
                        name,
                    )
                )

        return keys

    @staticmethod
    def _selected_metric_values(value, prefix=""):
        selected = {}
        search_terms = (
            "firstresponse",
            "totalresponse",
            "responsetime",
            "responsecount",
            "threadcount",
            "resolution",
            "closedtime",
            "onhold",
            "businesshour",
        )

        if isinstance(value, dict):
            for key, item in value.items():
                name = "%s.%s" % (prefix, key) if prefix else str(key)
                normalized = name.replace("_", "").lower()

                if (
                    any(term in normalized for term in search_terms)
                    and not isinstance(item, (dict, list))
                ):
                    selected[name] = item

                selected.update(
                    ZohoDashboardService._selected_metric_values(
                        item,
                        name,
                    )
                )
        elif isinstance(value, list):
            for index, item in enumerate(value[:3]):
                name = "%s[%s]" % (prefix, index)
                selected.update(
                    ZohoDashboardService._selected_metric_values(
                        item,
                        name,
                    )
                )

        return selected

    def get_ticket_metrics(self, ticket_id):
        url = f"{ZOHO_DESK_BASE}/tickets/{ticket_id}/metrics"
        return self._client.get(url)

    def diagnose_ticket_metrics_sample(
        self,
        sample_size=5,
    ):
        department_id = self.get_it_department_id(
            "Information Technology"
        )

        window = self.resolve_reporting_window(
            "last_24_hours"
        )

        tickets = self.get_created_tickets_for_window(
            window,
            department_id=department_id,
        )

        samples = []

        for ticket in tickets[:sample_size]:
            ticket_id = str(ticket.get("id") or "").strip()

            if not ticket_id:
                continue

            metrics = self.get_ticket_metrics(ticket_id)

            sample = {
                "ticket_id": ticket_id,
                "top_level_keys": (
                    sorted(metrics.keys())
                    if isinstance(metrics, dict)
                    else []
                ),
                "metric_field_names": self._flatten_metric_keys(metrics),
                "selected_metric_values": self._selected_metric_values(metrics),
            }

            _logger.info(
                "Zoho ticket metrics diagnostic sample: %s",
                sample,
            )

            samples.append(sample)

        return {
            "department_name": "Information Technology",
            "department_id": department_id,
            "period_key": window["period_key"],
            "timezone": window["timezone"],
            "window_start": window["window_start"].isoformat(),
            "window_end": window["window_end"].isoformat(),
            "sample_count": len(samples),
            "samples": samples,
        }
        return None

    @staticmethod
    def _format_avg_duration(seconds_list):
        if not seconds_list:
            return ""
        avg_seconds = sum(seconds_list) / len(seconds_list)
        hours, remainder = divmod(int(avg_seconds), 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{hours}h {minutes}m"

    # ------------------------------------------------------------------
    def get_full_dashboard_snapshot(
        self,
        start_date,
        end_date,
    ) -> dict:
        snapshot = {}

        it_dept_id = self.get_it_department_id(
            "Information Technology"
        )

        if not it_dept_id:
            raise ValueError(
                "Zoho Desk department 'Information Technology' "
                "was not found."
            )

        try:
            snapshot["ticket_count"] = (
                self.get_created_tickets_count(
                    start_date=start_date,
                    end_date=end_date,
                    department_id=it_dept_id,
                )
            )
        except Exception as exc:
            _logger.error(
                "Created tickets count sync failed: %s",
                exc,
                exc_info=True,
            )

        try:
            tickets = self.get_ticket_counts(
                start_date=start_date,
                end_date=end_date,
                department_id=it_dept_id,
            )

            snapshot.update({
                "new_tickets": tickets["new_tickets"],
                "on_hold_tickets": tickets["on_hold_tickets"],
                "closed_tickets": tickets["closed_tickets"],
                "backlog_tickets": tickets["backlog"],
            })
        except Exception as exc:
            _logger.error(
                "Ticket status sync failed: %s",
                exc,
                exc_info=True,
            )

        try:
            channels = self.get_channel_breakdown(
                start_date=start_date,
                end_date=end_date,
                department_id=it_dept_id,
            )

            snapshot.update({
                "tickets_from_web": channels["web"],
                "tickets_from_email": channels["email"],
                "tickets_from_phone": channels["phone"],
            })
        except Exception as exc:
            _logger.error(
                "Channel breakdown sync failed: %s",
                exc,
                exc_info=True,
            )

        try:
            snapshot.update(
                self.get_customer_happiness(
                    start_date=start_date,
                    end_date=end_date,
                    department_id=it_dept_id,
                )
            )
        except Exception as exc:
            _logger.error(
                "Customer happiness sync failed: %s",
                exc,
                exc_info=True,
            )

        try:
            snapshot.update(
                self.get_ticket_time_metrics(
                    start_date=start_date,
                    end_date=end_date,
                    department_id=it_dept_id,
                )
            )
        except Exception as exc:
            _logger.error(
                "Ticket time metrics sync failed: %s",
                exc,
                exc_info=True,
            )

        _logger.info(
            "Zoho full dashboard snapshot: "
            "department=%s range=%s to %s snapshot=%s",
            it_dept_id,
            start_date,
            end_date,
            snapshot,
        )

        return snapshot
