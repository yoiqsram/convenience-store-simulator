from datetime import datetime, timedelta

from .constants import DAYS_IN_YEAR


def add_years(dt: datetime, years: float) -> datetime:
    return dt + timedelta(days=int(years * DAYS_IN_YEAR))
