from datetime import date, datetime
from zoneinfo import ZoneInfo


def local_date(now_utc: datetime, tz: str) -> date:
    return now_utc.astimezone(ZoneInfo(tz)).date()


def iso_week(d: date) -> str:
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"
