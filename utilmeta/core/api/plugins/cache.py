from utype.types import *
from utilmeta.utils import Header, HTTP_METHODS, time_now
from utilmeta.utils import etag as etag_func
from utilmeta.utils import exceptions as exc
from utilmeta.core.request import Request
from utilmeta.core.response import Response
from .base import APIPlugin
from utype.parser.func import FunctionParser
from utype import type_transform
from utype.utils.exceptions import ParseError


class HttpCache(APIPlugin):
    function_parser_cls = FunctionParser

    NO_CACHE = "no-cache"
    NO_STORE = "no-store"
    NO_TRANSFORM = "no-transform"
    PUBLIC = "public"
    MAX_AGE = "max-age"
    MAX_STALE = "max-stale"
    MAX_FRESH = "max-fresh"
    PRIVATE = "private"
    MUST_REVALIDATE = "must-revalidate"

    def __init__(
        self,
        cache_control: str = PRIVATE,
        etag: bool = True,
        last_modified: bool = True,
        vary: Union[str, bool] = True,
        http_statuses: List[int] = (200, 204, 206),
        http_methods: List[str] = ("GET", "HEAD"),
        expiry_time: Union[int, datetime, timedelta, Callable, None] = 0,
    ):
        if expiry_time:
            if isinstance(expiry_time, (classmethod, staticmethod)):
                expiry_time = expiry_time.__func__
            assert isinstance(
                expiry_time, (int, float, datetime, timedelta)
            ) or callable(
                expiry_time
            ), f"Invalid Cache expiry_time: {expiry_time}, must be instance of int/datetime/timedelta or a callable"
            if callable(expiry_time):
                expiry_time = self.function_parser_cls.apply_for(expiry_time)
        if not cache_control or not isinstance(cache_control, str):
            raise ValueError(f'Cache control must be a valid string, got {type(cache_control)}')
        # use max hosts as max_variants to be part of locals()
        super().__init__(locals())
        self.cache_control = cache_control
        self.disable_etag = not etag
        self.disable_last_modified = not last_modified
        self.disable_vary = not vary
        self.vary_header = vary if isinstance(vary, str) else None
        self.included_statuses = [s for s in http_statuses if isinstance(s, int) and 100 <= s < 600]
        self.included_methods = [m.upper() for m in http_methods if m.upper() in HTTP_METHODS]
        self.expiry_time = expiry_time

    def get_max_age(self, request: Request):
        if self.expiry_time is None:
            return None
        if callable(self.expiry_time):
            max_age = self.expiry_time(request)
        else:
            max_age = self.expiry_time
        if isinstance(max_age, timedelta):
            max_age = max_age.total_seconds()
        elif isinstance(max_age, datetime):
            max_age = (max_age - time_now()).total_seconds()
        if isinstance(max_age, (int, float)):
            return int(max(max_age, 0))
        return None

    def process_response(self, response: Response):
        if response.event_stream:
            return response

        if response.status not in self.included_statuses:
            # consider it's not a valid response to operate or store
            return response
        if not response.request or response.request.method.upper() not in self.included_methods:
            return response

        request = response.request

        vary_header = response.headers.get(Header.VARY, self.vary_header)
        etag = response.headers.get(Header.ETAG)
        last_modified = response.headers.get(Header.LAST_MODIFIED)

        if not self.disable_last_modified:
            if_modified_since = request.headers.get(Header.IF_MODIFIED_SINCE)

            if last_modified:
                try:
                    last_modified = type_transform(last_modified, datetime)
                except ParseError:
                    last_modified = None
            if if_modified_since:
                try:
                    if_modified_since = type_transform(if_modified_since, datetime)
                except ParseError:
                    if_modified_since = None

            if last_modified and if_modified_since:
                if last_modified > if_modified_since:
                    return Response(status=304)

        if not self.disable_etag:
            # set etag
            if not etag:
                # SET ETAG
                vary_value = response.headers.get(vary_header) if vary_header and not self.disable_vary else None
                body = response.body
                try:
                    etag_content = ((str(vary_value) if vary_value else '') +
                                    (body.decode() if isinstance(body, bytes) else ''))
                except UnicodeDecodeError:
                    pass
                else:
                    etag = etag_func(etag_content)
                    response.set_header(Header.ETAG, etag)

            if_none_match = request.headers.get(Header.IF_NONE_MATCH)

            if etag and if_none_match:
                if if_none_match == etag:
                    return Response(status=304)

        cache_control = response.headers.get(Header.CACHE_CONTROL, self.cache_control)
        if etag or last_modified:
            if cache_control and 'max-age=' not in cache_control:
                max_age = self.get_max_age(request)
                if max_age is not None:
                    cache_control += f', max-age={max_age}'

        response.set_header(Header.CACHE_CONTROL, cache_control)
        return response
