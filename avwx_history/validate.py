"""
API parameter validators
"""

# pylint: disable=invalid-name

# stdlib
from datetime import date, datetime, timezone

# library
from voluptuous import (
    All,
    Boolean,
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
from avwx_api_core.validate import FlightRoute

REPORT_TYPES = ("metar", "taf")
FORMATS = ("json", "xml", "yaml")

HELP = {
    "format": f"Accepted response formats {FORMATS}",
    "date": "Date string formatted as YYYY-MM-DD",
    "parse": "Boolean to parse reports",
    "recent": "Returns most recent reports from a date (max 48)",
    "report_type": f"Weather report type {REPORT_TYPES}",
    "station": "ICAO station ID. Ex: KJFK",
    "route": "Flight route made of ICAO, navaid, or coordinate pairs. Ex: KLEX;ATL;29.2,-81.1;KMCO",
    "distance": "Statute miles from the route center",
}


def Date(value: str) -> date:
    """Validates a given date or returns the current one"""
    if not value:
        return datetime.now(tz=timezone.utc).date()
    try:
        return datetime.strptime(value, r"%Y-%m-%d").date()
    except ValueError as exc:
        raise Invalid(f"{value} is not a valid date with format YYYY-MM-DD") from exc


def Station(value: str) -> str:
    """Validation a station ICAO"""
    try:
        icao = Length(min=4, max=4)(value.upper())
        avwx.Station.from_icao(icao)
        return icao
    except (AttributeError, avwx.exceptions.BadStation, Invalid) as exc:
        raise Invalid(f"{value} is not a valid station ICAO") from exc


# pylint: disable=no-value-for-parameter

_required = {Required("format", default="json"): In(FORMATS)}
_dated = {
    Required("date", default=""): Date,
    Required("parse", default=True): Boolean(),
    Required("recent", default=0): All(Coerce(int), Range(min=0, max=48)),
    Required("report_type"): In(REPORT_TYPES),
}
_lookup = {Required("station"): Station}
_flight_path = {
    Required("distance"): All(Coerce(float), Range(min=0, max=100)),
    Required("route"): FlightRoute,
}


def _schema(schema: dict) -> Schema:
    return Schema(schema, extra=REMOVE_EXTRA)


lookup = _schema(_required | _dated | _lookup)
along = _schema(_required | _dated | _flight_path)
