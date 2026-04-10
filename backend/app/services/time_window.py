"""TimeWindowResolver — single source of truth for all time window math.

Every time boundary calculation (weekly, monthly, quarterly, yearly) must use
this utility.  Week starts Monday.  All boundaries are computed in the space's
local timezone, then converted to UTC for storage / querying.
"""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

Timeframe = Literal["weekly", "monthly", "quarterly", "yearly"]

_QUARTER_START_MONTH = {
    1: 1,
    2: 1,
    3: 1,
    4: 4,
    5: 4,
    6: 4,
    7: 7,
    8: 7,
    9: 7,
    10: 10,
    11: 10,
    12: 10,
}


class TimeWindowResolver:
    """Compute time windows (start/end in UTC) for a given IANA timezone."""

    def __init__(self, tz: str) -> None:
        self._tz = ZoneInfo(tz)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_current_window(
        self,
        timeframe: Timeframe,
        ref_date: datetime | date | None = None,
    ) -> tuple[datetime, datetime]:
        """Return ``(start_utc, end_utc)`` for the period containing *ref_date*.

        *ref_date* defaults to "now" in the space timezone.  If an aware
        ``datetime`` is passed it is first converted to the space timezone.
        """
        local_date = self._resolve_local_date(ref_date)
        start_local, end_local = self._window_boundaries(timeframe, local_date)
        return self._to_utc(start_local), self._to_utc(end_local)

    def get_previous_windows(
        self,
        timeframe: Timeframe,
        count: int = 3,
        ref_date: datetime | date | None = None,
    ) -> list[tuple[datetime, datetime]]:
        """Return *count* prior windows (most-recent first)."""
        local_date = self._resolve_local_date(ref_date)
        windows: list[tuple[datetime, datetime]] = []
        for i in range(1, count + 1):
            shifted = self._shift_back(timeframe, local_date, i)
            start_local, end_local = self._window_boundaries(timeframe, shifted)
            windows.append((self._to_utc(start_local), self._to_utc(end_local)))
        return windows

    def get_day_of_period(self, dt: datetime, timeframe: Timeframe) -> int:
        """Return the 1-based day index of *dt* within its period."""
        local_date = self._resolve_local_date(dt)
        start_local, _ = self._window_boundaries(timeframe, local_date)
        return (local_date - start_local.date()).days + 1

    def localize_for_display(self, dt_utc: datetime) -> datetime:
        """Convert a UTC datetime to the space timezone for display."""
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=UTC)
        return dt_utc.astimezone(self._tz)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_local_date(self, ref: datetime | date | None) -> date:
        """Normalise *ref* to a plain ``date`` in the space timezone."""
        if ref is None:
            return datetime.now(self._tz).date()
        if isinstance(ref, datetime):
            if ref.tzinfo is not None:
                return ref.astimezone(self._tz).date()
            return ref.date()
        return ref

    def _window_boundaries(
        self, timeframe: Timeframe, local_date: date
    ) -> tuple[datetime, datetime]:
        """Return (start, end) as *aware* datetimes in the space timezone."""
        if timeframe == "weekly":
            start_date = local_date - timedelta(days=local_date.weekday())
            end_date = start_date + timedelta(days=6)
        elif timeframe == "monthly":
            start_date = local_date.replace(day=1)
            last_day = calendar.monthrange(local_date.year, local_date.month)[1]
            end_date = local_date.replace(day=last_day)
        elif timeframe == "quarterly":
            q_start_month = _QUARTER_START_MONTH[local_date.month]
            start_date = date(local_date.year, q_start_month, 1)
            q_end_month = q_start_month + 2
            last_day = calendar.monthrange(local_date.year, q_end_month)[1]
            end_date = date(local_date.year, q_end_month, last_day)
        elif timeframe == "yearly":
            start_date = date(local_date.year, 1, 1)
            end_date = date(local_date.year, 12, 31)
        else:
            raise ValueError(f"Unknown timeframe: {timeframe!r}")

        start_dt = datetime.combine(start_date, time.min, tzinfo=self._tz)
        end_dt = datetime.combine(end_date, time(23, 59, 59, 999999), tzinfo=self._tz)
        end_dt = end_dt.replace(fold=1)  # Prefer post-DST occurrence
        return start_dt, end_dt

    def _shift_back(self, timeframe: Timeframe, local_date: date, n: int) -> date:
        """Shift *local_date* back by *n* periods."""
        if timeframe == "weekly":
            return local_date - timedelta(weeks=n)
        if timeframe == "monthly":
            return self._shift_months(local_date, -n)
        if timeframe == "quarterly":
            return self._shift_months(local_date, -3 * n)
        if timeframe == "yearly":
            return self._shift_years(local_date, -n)
        raise ValueError(f"Unknown timeframe: {timeframe!r}")

    @staticmethod
    def _shift_months(dt: date, months: int) -> date:
        """Add *months* (may be negative) with day-clamping."""
        total_months = (dt.year * 12 + dt.month - 1) + months
        new_year = total_months // 12
        new_month = total_months % 12 + 1
        max_day = calendar.monthrange(new_year, new_month)[1]
        return date(new_year, new_month, min(dt.day, max_day))

    @staticmethod
    def _shift_years(dt: date, years: int) -> date:
        """Shift by *years* with leap-year day clamping."""
        new_year = dt.year + years
        max_day = calendar.monthrange(new_year, dt.month)[1]
        return date(new_year, dt.month, min(dt.day, max_day))

    def _to_utc(self, dt: datetime) -> datetime:
        """Convert an aware space-timezone datetime to UTC."""
        return dt.astimezone(UTC)
