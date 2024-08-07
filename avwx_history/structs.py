"""Parameter dataclasses and types."""

# pylint: disable=missing-class-docstring

# stdlib
from dataclasses import dataclass
from datetime import date

# module
from avwx.structs import Coord
from avwx_api_core.structs import Params


DatedReports = list[tuple[date, str]]


@dataclass
class Dated(Params):
    date: date
    parse: bool
    report_type: str
    recent: int


@dataclass
class Lookup(Dated):
    station: str


@dataclass
class FlightRoute(Dated):
    route: list[Coord]
    distance: float
