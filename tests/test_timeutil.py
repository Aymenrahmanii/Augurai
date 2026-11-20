from datetime import UTC, date, datetime

from augurai.timeutil import iso_week, local_date


def test_local_date_crosses_midnight():
    now = datetime(2026, 11, 20, 23, 30, tzinfo=UTC)
    assert local_date(now, "Africa/Tunis") == date(2026, 11, 21)


def test_iso_week():
    assert iso_week(date(2026, 11, 20)) == "2026-W47"
