"""
Expand history objects into dates and save only raw report
"""

# stdlib
from datetime import datetime
from os import environ
from typing import Dict

# library
from pymongo import MongoClient, UpdateOne


def make_update(icao: str, date: datetime, reports: Dict[str, dict]) -> UpdateOne:
    """
    Returns an UpdateOne operation for stripped reports on a day
    """
    reports = {key: val["raw"] for key, val in reports.items()}
    return UpdateOne(
        {"icao": icao, "date": date}, {"$set": {"raw": reports}}, upsert=True,
    )


def main() -> int:
    """
    Expand history objects into dates and save only raw report
    """
    mdb = MongoClient(environ["MONGO_URI"])
    while item := mdb.history.metar.find_one({"date": {"$exists": False}}):
        icao = item.pop("_id")
        print(icao)
        updates = []
        for year, months in item.items():
            for month, days in months.items():
                for day, reports in days.items():
                    date = datetime(int(year), int(month), int(day))
                    updates.append(make_update(icao, date, reports))
        print(icao, len(updates))
        mdb.history.metar.bulk_write(updates, ordered=False)
        print("Deleting")
        mdb.history.metar.delete_one({"_id": icao})
    return 0


if __name__ == "__main__":
    main()
