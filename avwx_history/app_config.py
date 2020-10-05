"""
AVWX app configuration and lifecycle
"""

# stdlib
from os import environ

# library
# from motor.motor_asyncio import AsyncIOMotorClient

# module
from avwx_api_core.app import create_app
from avwx_api_core.cache import CacheManager
from avwx_api_core.token import TokenManager
from avwx_history.history import HistoryFetch

app = create_app(__name__, environ.get("MONGO_URI"))


@app.before_serving
async def init_helpers():
    """
    Init API helpers
    """
    app.cache = CacheManager(app)
    app.token = TokenManager(app)
    app.history = HistoryFetch(app)
    # app.archive = AsyncIOMotorClient(environ.get("MONGO_ARCHIVE_URI"))
