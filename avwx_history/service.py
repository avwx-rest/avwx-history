"""Historic report services."""

# stdlib
import datetime as dt

# module
from avwx.service.scrape import CallsHTTP, NoaaScrapeList
from avwx_history.structs import DatedReports


class NOAA(NoaaScrapeList):
    """Fetch recent reports from NOAA."""

    _valid_types = ("metar", "taf", "pirep")

    def _make_url(self, station: str, **kwargs: int | str) -> tuple[str, dict]:
        """Return a formatted URL and parameters."""
        hours = 28
        params = {"ids": station, "format": "raw", "hours": hours, **kwargs}
        return self._url.format(self.report_type), params


class Agron(CallsHTTP):
    """Source reports from agron server."""

    url = (
        "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?"
        "station={}&data=metar&"
        "year1={}&month1={}&day1={}&"
        "year2={}&month2={}&day2={}&"
        "tz=Etc%2FUTC&format=onlycomma&latlon=no&missing=null&"
        "trace=null&direct=no&report_type=1&report_type=2"
    )

    @staticmethod
    def find_timestamp(report: str) -> str | None:
        """Return the Zulu timestamp without the trailing Z."""
        for item in report.split():
            if len(item) == 7 and item.endswith("Z") and item[:6].isdigit():
                return item[:6]
        return None

    def parse_response(self, text: str) -> DatedReports:
        """Return valid reports from the raw response as date tuples."""
        lines = text.strip().split("\n")[1:]
        data: dict[dt.date, dict[str, str]] = {}
        for line in lines:
            items = line.split(",")
            date_key = dt.datetime.strptime(items[1].split()[0], r"%Y-%m-%d").date()
            report = " ".join(items[2].split())
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

    async def date_range(self, code: str, start: dt.date, end: dt.date) -> DatedReports:
        """Return dated reports between start and not including end dates."""
        url = self.url.format(
            code,
            start.year,
            start.month,
            start.day,
            end.year,
            end.month,
            end.day,
        )
        text = await self._call(url)
        return self.parse_response(text)

    async def by_date(self, code: str, date: dt.date) -> DatedReports:
        """Return dated reports on a specific date."""
        end = date + dt.timedelta(days=1)
        return await self.date_range(code, date, end)
