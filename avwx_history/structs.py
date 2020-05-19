"""
Parameter dataclasses
"""

# stdlib
from dataclasses import dataclass
from datetime import date


@dataclass
class DateParams:
    date: date
    parse: bool
    report_type: str
    station: str
    recent: int = None
