"""
API parameter validators
"""

# stdlib
from datetime import date, datetime, timezone

# library
from voluptuous import (
    All,
    Schema,
    Coerce,
    In,
    Invalid,
    Length,
    Range,
    Required,
    REMOVE_EXTRA,
)

# module
import avwx

REPORT_TYPES = ("metar", "taf")


def Date(value: str) -> date:
    """
    Validates a given date or returns the current one
    """
    if not value:
        return datetime.now(tz=timezone.utc).date()
    try:
        return datetime.strptime(value, r"%Y-%m-%d").date()
    except ValueError:
        raise Invalid(f"{value} is not a valid date with format YYYY-MM-DD")


def Station(value: str) -> str:
    """
    Validation a station ICAO
    """
    try:
        icao = Length(min=4, max=4)(value.upper())
        avwx.Station.from_icao(icao)
        return icao
    except (AttributeError, avwx.exceptions.BadStation, Invalid):
        raise Invalid(f"{value} is not a valid station ICAO")


date_params = Schema(
    {
        Required("date", default=""): Date,
        Required("station"): Station,
        Required("report_type"): In(REPORT_TYPES),
        "recent": All(Coerce(int), Range(min=1, max=48)),
    },
    extra=REMOVE_EXTRA,
)

HELP = {
    "date": "Date string formatted as YYYY-MM-DD",
    "recent": "Returns most recent reports from a date (max 48)",
    "report_type": "Weather report type (metar, taf)",
    "station": "ICAO station ID. Ex: KJFK",
}
