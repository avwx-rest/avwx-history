"""
History fetch manager
"""

# stdlib
import datetime as dt
from dataclasses import asdict

# module
import avwx
from avwx_api_core.util.handler import mongo_handler


PARSER = {
    "metar": avwx.Metar,
    "taf": avwx.Taf,
}


class HistoryFetch:
    """
    Manages fetching historic reports
    """

    def __init__(self, app: "Quart"):
        self._app = app

    async def by_date(
        self, report_type: str, icao: str, date: "date"
    ) -> [(str, dt.date)]:
        """
        Fetch station reports by date
        """
        date = dt.datetime(date.year, date.month, date.day)
        fetch = self._app.mdb.history[report_type].find_one(
            {"icao": icao, "date": date}, {"_id": 0, "raw": 1}
        )
        data = await mongo_handler(fetch)
        if not data or "raw" not in data:
            return []
        date = date.date()
        return [
            (i[1], date)
            for i in sorted(data["raw"].items(), key=lambda x: x[0][0], reverse=True)
        ]

    async def recent(
        self, report_type: str, icao: str, date: "date", count: int
    ) -> [(str, dt.date)]:
        """
        Fetch most recent n reports from a date
        """
        data = await self.by_date(report_type, icao, date) or []
        while len(data) <= count:
            date = date - dt.timedelta(days=1)
            new_data = await self.by_date(report_type, icao, date)
            if not new_data:
                break
            data += [(item, date.date()) for item in new_data]
        if len(data) > count:
            data = data[:count]
        return data

    async def from_params(self, params: "structs.Params") -> [dict]:
        """
        Fetch reports based on request params
        """
        kwargs = {
            "report_type": params.report_type,
            "icao": params.station,
            "date": params.date,
        }
        if params.recent:
            data = await self.recent(**kwargs, count=params.recent)
        else:
            data = await self.by_date(**kwargs)
        parser = PARSER[params.report_type]
        ret = []
        for report, date in data:
            if params.parse:
                ret.append(asdict(parser.from_report(report, issued=date).data))
            else:
                ret.append(parser.sanitize(report))
        return ret
