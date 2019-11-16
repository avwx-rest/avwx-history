"""
History fetch manager
"""

# stdlib
from datetime import timedelta

# module
from avwx_api_core.util.handler import mongo_handler


class HistoryFetch:
    """
    Manages fetching historic reports
    """

    def __init__(self, app: "Quart"):
        self._app = app

    async def by_date(self, report_type: str, icao: str, date: "date") -> [dict]:
        """
        Fetch station reports by date
        """
        key = f"{date.year}.{date.month}.{date.day}"
        op = self._app.mdb.history[report_type].find_one(
            {"_id": icao}, {"_id": 0, key: 1}
        )
        data = await mongo_handler(op)
        try:
            for sub in key.split("."):
                data = data[sub]
        except (KeyError, TypeError):
            return
        if not data:
            return
        return [i[1] for i in sorted(data.items(), key=lambda x: x[0], reverse=True)]

    async def recent(
        self, report_type: str, icao: str, date: "date", count: int
    ) -> [dict]:
        """
        Fetch most recent n reports from a date
        """
        data = await self.by_date(report_type, icao, date) or []
        while len(data) <= count:
            date = date - timedelta(days=1)
            new_data = await self.by_date(report_type, icao, date)
            if not new_data:
                break
            data += new_data
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
        return data or []
