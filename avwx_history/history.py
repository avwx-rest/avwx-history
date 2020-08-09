"""
History fetch manager
"""

# stdlib
import datetime as dt
from dataclasses import asdict
from typing import List, Tuple

# library
from quart import Quart

# module
import avwx
from avwx_api_core.util.handler import mongo_handler
from avwx_history.structs import DateParams


PARSER = {
    "metar": avwx.Metar,
    "taf": avwx.Taf,
}


class NOAA(avwx.service.NOAA_ADDS):
    """
    Fetch recent reports from NOAA ADDS
    """

    _coallate = ("metar", "taf", "aircraftreport")

    def _make_url(self, station: str, lat: float, lon: float) -> Tuple[str, dict]:
        """
        Returns a formatted URL and parameters
        """
        # Base request params
        params = {
            "requestType": "retrieve",
            "format": "XML",
            "hoursBeforeNow": 28,
            "dataSource": self.report_type + "s",
            "stationString": station,
        }
        return self.url, params


def find_date(report: str) -> dt.date:
    """
    Returns the Zulu timestamp without the trailing Z
    """
    for item in report.split():
        if len(item) == 7 and item.endswith("Z") and item[:6].isdigit():
            if timestamp := item[:6]:
                return avwx.parsing.core.parse_date(timestamp).date()
    return None


DatedReports = List[Tuple[dt.date, str]]


class HistoryFetch:
    """
    Manages fetching historic reports
    """

    def __init__(self, app: Quart):
        self._app = app

    async def recent_from_noaa(self, report_type: str, icao: str) -> DatedReports:
        """
        Fetch recent reports from NOAA, not storage
        """
        service = NOAA(report_type)
        reports = await service.async_fetch(icao)
        if not reports:
            return []
        ret = []
        for report in reports:
            if date := find_date(report):
                ret.append((date, report))
        return ret

    async def by_date(self, report_type: str, icao: str, date: dt.date) -> DatedReports:
        """
        Fetch station reports by date
        """
        date = dt.datetime(date.year, date.month, date.day)
        fetch = self._app.archive.history[report_type].find_one(
            {"icao": icao, "date": date}, {"_id": 0, "raw": 1}
        )
        data = await mongo_handler(fetch)
        if not data or "raw" not in data:
            return []
        date = date.date()
        return [(date, report) for report in data["raw"].values()]

    async def recent(
        self, report_type: str, icao: str, date: dt.date, count: int
    ) -> DatedReports:
        """
        Fetch most recent n reports from a date
        """
        today = dt.datetime.now(tz=dt.timezone.utc).date()
        if today - date < dt.timedelta(days=2):
            data = await self.recent_from_noaa(report_type, icao)
        else:
            data = await self.by_date(report_type, icao, date) or []
        while len(data) <= count:
            date = date - dt.timedelta(days=1)
            new_data = await self.by_date(report_type, icao, date)
            if not new_data:
                break
            data += new_data
            data = list(set(data))
        if len(data) > count:
            data = data[:count]
        return data

    async def from_params(self, params: DateParams) -> List[dict]:
        """
        Fetch reports based on request params
        """
        kwargs = {
            "report_type": params.report_type,
            "icao": params.station,
            "date": params.date,
        }
        today = dt.datetime.now(tz=dt.timezone.utc).date()
        if params.recent:
            data = await self.recent(**kwargs, count=params.recent)
        elif params.date == today:
            data = await self.recent_from_noaa(params.report_type, params.station)
            data = list(set(i for i in data if i[0] == today))
        else:
            data = await self.by_date(**kwargs)
        data.sort(reverse=True)
        parser = PARSER[params.report_type]
        ret = []
        for date, report in data:
            if params.parse:
                ret.append(asdict(parser.from_report(report, issued=date).data))
            else:
                ret.append(parser.sanitize(report))
        return ret
