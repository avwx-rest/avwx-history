"""
API parameter validators
"""

# stdlib
from datetime import date, datetime, timezone

# library
from voluptuous import Schema, In, Invalid, Length, Required, REMOVE_EXTRA

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
    Performs a crude validation of a station ICAO
    """
    try:
        return Length(min=4, max=4)(value.upper())
    except (AttributeError, Invalid):
        raise Invalid(f"{value} is not a valid station ICAO")


date_params = Schema(
    {
        Required("date", default=""): Date,
        "station": Station,
        "report_type": In(REPORT_TYPES),
    },
    extra=REMOVE_EXTRA,
)

HELP = {
    "date": "Date string formatted as YYYY-MM-DD",
    "report_type": "Weather report type (metar, taf)",
    "station": "ICAO station ID. Ex: KJFK",
}
