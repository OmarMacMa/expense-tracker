from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.services.time_window import TimeWindowResolver


class TestWeeklyWindow:
    def test_basic_weekly(self):
        """Basic weekly window starts Monday, ends Sunday."""
        r = TimeWindowResolver("UTC")
        # Wednesday March 19, 2026
        ref = datetime(2026, 3, 19, 12, 0, tzinfo=UTC)
        start, end = r.get_current_window("weekly", ref)
        # Should be Mon Mar 16 - Sun Mar 22
        assert start.weekday() == 0  # Monday
        assert end.date().isoformat() == "2026-03-22"

    def test_dst_spring_forward(self):
        """Week spanning US DST spring-forward (March 2026, 2nd Sunday March 8)."""
        r = TimeWindowResolver("America/New_York")
        # March 10, 2026 (Tuesday after spring forward)
        ref = datetime(2026, 3, 10, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        start, end = r.get_current_window("weekly", ref)
        # Window should be valid (start < end, both UTC)
        assert start < end
        # Start should be Monday March 9 in ET
        start_local = start.astimezone(ZoneInfo("America/New_York"))
        assert start_local.weekday() == 0

    def test_dst_fall_back(self):
        """Week spanning US DST fall-back (November 2026, 1st Sunday Nov 1)."""
        r = TimeWindowResolver("America/New_York")
        ref = datetime(2026, 11, 3, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        start, end = r.get_current_window("weekly", ref)
        assert start < end

    def test_year_boundary_week(self):
        """Week starting in December, ending in January."""
        r = TimeWindowResolver("UTC")
        # Dec 31, 2025 is a Wednesday
        ref = datetime(2025, 12, 31, 12, 0, tzinfo=UTC)
        start, end = r.get_current_window("weekly", ref)
        assert start.year == 2025
        assert end.year == 2026


class TestMonthlyWindow:
    def test_basic_monthly(self):
        """Monthly window spans 1st to last day."""
        r = TimeWindowResolver("UTC")
        ref = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
        start, end = r.get_current_window("monthly", ref)
        assert start.day == 1
        assert end.day == 31  # March has 31 days

    def test_february_leap_year(self):
        """February in a leap year has 29 days."""
        r = TimeWindowResolver("UTC")
        ref = datetime(2028, 2, 15, 12, 0, tzinfo=UTC)  # 2028 is leap
        start, end = r.get_current_window("monthly", ref)
        assert start.day == 1
        assert end.day == 29

    def test_february_non_leap(self):
        """February in a non-leap year has 28 days."""
        r = TimeWindowResolver("UTC")
        ref = datetime(2026, 2, 15, 12, 0, tzinfo=UTC)
        start, end = r.get_current_window("monthly", ref)
        assert end.day == 28

    def test_first_day_of_month(self):
        """ref_date on the first day returns same month."""
        r = TimeWindowResolver("UTC")
        ref = datetime(2026, 3, 1, 0, 0, tzinfo=UTC)
        start, end = r.get_current_window("monthly", ref)
        assert start.month == 3
        assert end.month == 3

    def test_last_day_of_month(self):
        """ref_date on the last day returns same month."""
        r = TimeWindowResolver("UTC")
        ref = datetime(2026, 3, 31, 23, 59, tzinfo=UTC)
        start, end = r.get_current_window("monthly", ref)
        assert start.month == 3
        assert end.month == 3


class TestQuarterlyWindow:
    def test_q1(self):
        r = TimeWindowResolver("UTC")
        ref = datetime(2026, 2, 15, 12, 0, tzinfo=UTC)
        start, end = r.get_current_window("quarterly", ref)
        assert start.month == 1 and start.day == 1
        assert end.month == 3 and end.day == 31

    def test_q4_to_q1_transition(self):
        """Previous window from Q1 should be Q4 of prior year."""
        r = TimeWindowResolver("UTC")
        ref = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
        prev = r.get_previous_windows("quarterly", count=1, ref_date=ref)
        assert len(prev) == 1
        prev_start, prev_end = prev[0]
        assert prev_start.month == 10  # Q4 start
        assert prev_end.year == 2025


class TestPreviousWindows:
    def test_previous_3_months(self):
        r = TimeWindowResolver("UTC")
        ref = datetime(2026, 4, 15, 12, 0, tzinfo=UTC)
        prev = r.get_previous_windows("monthly", count=3, ref_date=ref)
        assert len(prev) == 3
        months = [p[0].month for p in prev]
        assert months == [3, 2, 1]

    def test_previous_weekly(self):
        r = TimeWindowResolver("UTC")
        ref = datetime(2026, 3, 19, 12, 0, tzinfo=UTC)
        prev = r.get_previous_windows("weekly", count=2, ref_date=ref)
        assert len(prev) == 2
        # Each should be a valid week
        for start, end in prev:
            assert start < end
            assert start.astimezone(UTC).weekday() == 0  # Monday


class TestDayOfPeriod:
    def test_first_day(self):
        r = TimeWindowResolver("UTC")
        ref = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
        assert r.get_day_of_period(ref, "monthly") == 0

    def test_mid_month(self):
        r = TimeWindowResolver("UTC")
        ref = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
        assert r.get_day_of_period(ref, "monthly") == 14


class TestEdgeTimezones:
    def test_utc_no_dst(self):
        """UTC has no DST transitions."""
        r = TimeWindowResolver("UTC")
        start, end = r.get_current_window("weekly")
        assert start < end

    def test_utc_plus_13(self):
        """Pacific/Tongatapu (UTC+13) — ahead of UTC."""
        r = TimeWindowResolver("Pacific/Tongatapu")
        start, end = r.get_current_window("monthly")
        assert start < end

    def test_utc_minus_12(self):
        """Etc/GMT+12 (UTC-12) — behind UTC."""
        r = TimeWindowResolver("Etc/GMT+12")
        start, end = r.get_current_window("weekly")
        assert start < end


class TestLocalizeForDisplay:
    def test_utc_to_eastern(self):
        r = TimeWindowResolver("America/New_York")
        utc_dt = datetime(2026, 3, 15, 17, 0, tzinfo=UTC)
        local = r.localize_for_display(utc_dt)
        assert local.tzinfo is not None
        # In March (EDT), UTC-4
        assert local.hour == 13
