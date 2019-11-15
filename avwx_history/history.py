"""
History fetch manager
"""

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
        return [i[1] for i in sorted(data.items(), key=lambda x: x[0])]
