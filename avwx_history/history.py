"""
History fetch manager
"""

# stdlib
import datetime as dt
from dataclasses import asdict
from typing import List, Tuple

# library
import httpx
from quart import Quart

# module
import avwx

# from avwx_api_core.util.handler import mongo_handler
from avwx_history.structs import DateParams


PARSER = {
    "metar": avwx.Metar,
    "taf": avwx.Taf,
}


class NOAA(avwx.service.NOAA_ADDS):
    """Fetch recent reports from NOAA ADDS"""

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
    """Returns the Zulu timestamp without the trailing Z"""
    for item in report.split():
        if len(item) == 7 and item.endswith("Z") and item[:6].isdigit():
            if timestamp := item[:6]:
                return avwx.parsing.core.parse_date(timestamp).date()
    return None


DatedReports = List[Tuple[dt.date, str]]


class Agron:
    """Source reports from agron server"""

    url = (
        "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?"
        "station={}&data=metar&"
        "year1={}&month1={}&day1={}&"
        "year2={}&month2={}&day2={}&"
        "tz=Etc%2FUTC&format=onlycomma&latlon=no&missing=null&"
        "trace=null&direct=no&report_type=1&report_type=2"
    )

    @staticmethod
    def find_timestamp(report: str) -> str:
        """Returns the Zulu timestamp without the trailing Z"""
        for item in report.split():
            if len(item) == 7 and item.endswith("Z") and item[:6].isdigit():
                return item[:6]
        return None

    def parse_response(self, text: str) -> DatedReports:
        """Returns valid reports from the raw response as date tuples"""
        lines = text.strip().split("\n")[1:]
        data = {}
        for line in lines:
            line = line.split(",")
            date_key = dt.datetime.strptime(line[1].split()[0], r"%Y-%m-%d").date()
            report = " ".join(line[2].split())
            # Source includes "null" lines and fake data
            # NOTE: https://mesonet.agron.iastate.edu/onsite/news.phtml?id=1290
            if not report or report == "null" or "MADISHF" in report:
                continue
            report_key = self.find_timestamp(report)
            if not report_key:
                continue
            try:
                data[date_key][report_key] = report
            except KeyError:
                data[date_key] = {report_key: report}
        ret = []
        for key, reports in data.items():
            ret += [(key, val) for val in sorted(reports.values())]
        return ret

    async def date_range(self, icao: str, start: dt.date, end: dt.date) -> DatedReports:
        """Return dated reports between start and not including end dates"""
        url = self.url.format(
            icao, start.year, start.month, start.day, end.year, end.month, end.day,
        )
        try:
            async with httpx.AsyncClient() as conn:
                resp = await conn.get(url)
        except:
            return []
        return self.parse_response(resp.text)

    async def by_date(self, icao: str, date: dt.date) -> DatedReports:
        """Return dated reports on a specific date"""
        end = date + dt.timedelta(days=1)
        return await self.date_range(icao, date, end)

class HistoryFetch:
    """Manages fetching historic reports"""

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
        """Fetch station reports by date"""
        agron = Agron()
        return await agron.by_date(icao, date)
        # date = dt.datetime(date.year, date.month, date.day)
        # fetch = self._app.mdb.history[report_type].find_one(
        #     {"icao": icao, "date": date}, {"_id": 0, "raw": 1}
        # )
        # data = await mongo_handler(fetch)
        # if not data or "raw" not in data:
        #     return []
        # date = date.date()
        # return [(date, report) for report in data["raw"].values()]

    async def recent(
        self, report_type: str, icao: str, date: dt.date, count: int
    ) -> DatedReports:
        """Fetch most recent n reports from a date"""
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
        """Fetch reports based on request params"""
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
