"""History fetch manager."""

# stdlib
import asyncio as aio
import datetime as dt
from contextlib import suppress
from dataclasses import asdict
from typing import Any, Coroutine, Optional, Union

# library
from quart import Quart

# module
import avwx
from avwx_api_core.services import FlightRouter

# from avwx_api_core.util.handler import mongo_handler
from avwx_history.service import Agron, NOAA
from avwx_history.structs import DatedReports, FlightRoute, Lookup


PARSER = {
    "metar": avwx.Metar,
    "taf": avwx.Taf,
}


def find_date(report: str) -> Optional[dt.date]:
    """Return the Zulu timestamp without the trailing Z."""
    for item in report.split():
        if len(item) == 7 and item.endswith("Z") and item[:6].isdigit():
            if timestamp := item[:6]:
                return avwx.parsing.core.parse_date(timestamp).date()
    return None


async def gather_with_concurrency(concurrent: int, *tasks: Coroutine) -> list[Any]:
    """Run max number of coroutines at one time. Replaces aio.gather."""
    semaphore = aio.Semaphore(concurrent)

    async def sem_task(task):
        async with semaphore:
            return await task

    return await aio.gather(*(sem_task(task) for task in tasks))


class HistoryFetch:
    """Manage fetching historic reports."""

    def __init__(self, app: Quart):
        self._app = app

    @staticmethod
    async def recent_from_noaa(report_type: str, code: str) -> DatedReports:
        """Fetch recent reports from NOAA, not storage."""
        service = NOAA(report_type)
        reports = await service.async_fetch(code)
        if not reports:
            return []
        ret = []
        for report in reports:
            if date := find_date(report):
                ret.append((date, report))
        return ret

    @staticmethod
    async def by_date(report_type: str, code: str, date: dt.date) -> DatedReports:
        """Fetch station reports by date."""
        agron = Agron()
        return await agron.by_date(code, date)
        # date = dt.datetime(date.year, date.month, date.day)
        # fetch = self._app.mdb.history[report_type].find_one(
        #     {"code": code, "date": date}, {"_id": 0, "raw": 1}
        # )
        # data = await mongo_handler(fetch)
        # if not data or "raw" not in data:
        #     return []
        # date = date.date()
        # return [(date, report) for report in data["raw"].values()]

    async def recent(
        self, report_type: str, code: str, date: dt.date, count: int
    ) -> DatedReports:
        """Fetch most recent n reports from a date."""
        today = dt.datetime.now(tz=dt.timezone.utc).date()
        if today - date < dt.timedelta(days=2):
            data = await self.recent_from_noaa(report_type, code)
        else:
            data = await self.by_date(report_type, code, date) or []
        while len(data) <= count:
            date = date - dt.timedelta(days=1)
            new_data = await self.by_date(report_type, code, date)
            if not new_data:
                break
            data += new_data
            data = list(set(data))
        if len(data) > count:
            data = data[:count]
        return data

    async def from_params(
        self, params: Lookup, station: Optional[str] = None
    ) -> list[dict]:
        """Fetch reports based on request params."""
        code = getattr(params, "station", station)
        if not code:
            msg = "No station code found"
            raise ValueError(msg)
        today = dt.datetime.now(tz=dt.timezone.utc).date()
        if params.recent:
            data = await self.recent(
                report_type=params.report_type,
                code=code,
                date=params.date,
                count=params.recent,
            )
        elif params.date == today:
            data = await self.recent_from_noaa(params.report_type, params.station)
            data = list(set(i for i in data if i[0] == today))
        else:
            data = await self.by_date(
                report_type=params.report_type,
                code=code,
                date=params.date,
            )
        data.sort(reverse=True)
        parser = PARSER[params.report_type]
        ret = []
        for date, report in data:
            if params.parse:
                ret.append(asdict(parser.from_report(report, issued=date).data))
            else:
                ret.append(parser.sanitize(report))
        return ret

    @staticmethod
    def _find_station(report: Union[dict, str]) -> str:
        if isinstance(report, dict):
            return report["station"]
        for item in report.split():
            with suppress(avwx.station.valid_station(item)):
                return item
        return ""

    async def flight_route(self, params: FlightRoute) -> dict[str, list]:
        """Fetch reports along a flight path."""
        stations = await FlightRouter().fetch("station", params.distance, params.route)
        tasks = [self.from_params(params, s) for s in stations]
        reports: list[list[dict]] = await gather_with_concurrency(20, *tasks)
        return {self._find_station(r[0]): r for r in reports if r}
