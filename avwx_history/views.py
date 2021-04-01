"""
API view handlers
"""

# stdlib
from datetime import datetime, timezone
from functools import wraps

# library
from quart import redirect, request, Response
from quart_openapi.cors import crossdomain
from voluptuous import Invalid, MultipleInvalid

# module
from avwx_api_core.views import AuthView, make_token_check
from avwx_history import app, structs, validate

token_check = make_token_check(app)

HEADERS = ["Authorization", "Content-Type"]


def parse_params(func):
    """Collects and parses endpoint parameters"""

    @wraps(func)
    async def wrapper(self, **kwargs):
        params = self.validate_params(**kwargs)
        if isinstance(params, dict):
            return self.make_response(params, code=400)
        return await func(self, params)

    return wrapper


_key_repl = {"base": "altitude"}
_key_remv = ["top"]


class Base(AuthView):
    """Base historic reports view"""

    validator: validate.Schema
    struct: structs.Params
    plan_types = ("enterprise",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._key_repl = _key_repl
        self._key_remv = _key_remv

    def validate_params(self, **kwargs):
        """Returns all validated request parameters or an error response dict"""
        try:
            params = {**request.args, **kwargs}
            return self.struct(**self.validator(params))
        except (Invalid, MultipleInvalid) as exc:
            key = str(exc.path[0])
            return {"error": str(exc.msg), "param": key, "help": validate.HELP.get(key)}


@app.route("/api/<report_type>/<station>")
class Lookup(Base):
    """Handle single-station lookups"""

    validator = validate.lookup
    struct = structs.Lookup

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params) -> Response:
        """GET handler returning reports for a specific station"""
        reports = await app.history.from_params(params)
        data = {
            "meta": datetime.now(tz=timezone.utc),
            "results": reports,
        }
        return self.make_response(data)


@app.route("/api/path/<report_type>")
class Along(Base):
    """Handle lookups along a flight path"""

    validator = validate.along
    struct = structs.FlightRoute

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params) -> Response:
        """GET handler returning reports along a flight path"""
        reports = await app.history.flight_route(params)
        data = {
            "meta": datetime.now(tz=timezone.utc),
            "route": params.route,
            "results": reports,
        }
        return self.make_response(data)


@app.route("/")
def home():
    """Redirect to AVWX home"""
    return redirect("https://avwx.rest")
