"""
AVWX app configuration and lifecycle
"""

# stdlib
from os import environ

# library
import rollbar

# from motor.motor_asyncio import AsyncIOMotorClient
from quart import got_request_exception
from rollbar.contrib.quart import report_exception

# module
from avwx_api_core.app import create_app
from avwx_api_core.cache import CacheManager
from avwx_api_core.token import TokenManager
from avwx_history.history import HistoryFetch

app = create_app(__name__, environ.get("MONGO_URI"))


@app.before_serving
async def init_helpers():
    """Init API helpers"""
    app.cache = CacheManager(app)
    app.token = TokenManager(app)
    app.history = HistoryFetch(app)
    # app.archive = AsyncIOMotorClient(environ.get("MONGO_ARCHIVE_URI"))


@app.before_first_request
def init_rollbar():
    """Initialize Rollbar exception logging"""
    key = environ.get("LOG_KEY")
    if not (key and app.env == "production"):
        return
    rollbar.init(key, root="avwx_history", allow_logging_basic_config=False)
    got_request_exception.connect(report_exception, app, weak=False)
