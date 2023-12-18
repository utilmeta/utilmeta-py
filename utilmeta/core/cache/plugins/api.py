from utilmeta.utils import pop, get_interval, Header, time_now, http_time, COMMON_ERRORS, fast_digest
from utype import type_transform
from utype.parser.func import FunctionParser
from utilmeta.utils import exceptions as exc
from typing import Union, Callable, Optional, List, Type, TYPE_CHECKING
from datetime import datetime, timedelta, timezone, date
import warnings
from .base import BaseCacheInterface
from .entity import CacheEntity

if TYPE_CHECKING:
    from utilmeta.core.request import Request

NUM_TYPES = (int, float)
NUM = Union[int, float]
VAL = Union[str, bytes, list, tuple, dict]

__all__ = ['ServerCache']


NOT_MODIFIED_KEEP_HEADERS = (
    "Cache-Control",
    "Content-Location",
    "Date",
    "ETag",
    "Expires",
    "Last-Modified",
    "Vary",
)


class ServerCache(BaseCacheInterface):
    NO_CACHE = 'no-cache'
    NO_STORE = 'no-store'
    NO_TRANSFORM = 'no-transform'
    PUBLIC = 'public'
    MAX_AGE = 'max-age'
    MAX_STALE = 'max-stale'
    MAX_FRESH = 'max-fresh'
    PRIVATE = 'private'
    MUST_REVALIDATE = 'must-revalidate'

    # volatile strategy
    OBSOLETE_LRU = 'LRU'    # least recently updated
    OBSOLETE_LFU = 'LFU'    # least frequently used
    OBSOLETE_RANDOM = 'RANDOM'

    # omit
    OMIT_ARG_NAMES = ('self', 'cls', 'mcs')
    FOREVER_TIMEDELTA = timedelta(days=365 * 50)

    # standard vary
    VARY_COOKIE = Header.COOKIE
    VARY_LANGUAGE = Header.ACCEPT_LANGUAGE
    VARY_UA = Header.USER_AGENT
    VARY_ACCEPT = Header.ACCEPT
    VARY_ENCODING = Header.ACCEPT_ENCODING
    VARY_REFERER = Header.REFERER

    function_parser_cls = FunctionParser

    # vary functions
    @classmethod
    def vary_user(cls, request):
        return request.user_id

    @classmethod
    def vary_session(cls, request):
        return request.session.session_key

    @classmethod
    def expires_next_minute(cls):
        current_time = time_now()
        return datetime(
            year=current_time.year,
            month=current_time.month,
            day=current_time.day,
            hour=current_time.hour,
            minute=current_time.minute
        ) + timedelta(minutes=1)

    @classmethod
    def expires_next_hour(cls):
        current_time = time_now()
        return datetime(
            year=current_time.year,
            month=current_time.month,
            day=current_time.day,
            hour=current_time.hour
        ) + timedelta(hours=1)

    @classmethod
    def expires_next_day(cls):
        current_time = time_now()
        return datetime(
            year=current_time.year,
            month=current_time.month,
            day=current_time.day,
            hour=0
        ) + timedelta(days=1)

    @classmethod
    def expires_next_week(cls):
        current_time = time_now()
        delta_days = 7 - current_time.weekday()
        return datetime(
            year=current_time.year,
            month=current_time.month,
            day=current_time.day,
            hour=0
        ) + timedelta(days=delta_days)

    @classmethod
    def expires_next_month(cls):
        current_time = time_now()
        if current_time.month == 12:
            year = current_time.year + 1
            month = 1
        else:
            year = current_time.year
            month = current_time.month + 1
        return datetime(
            year=year,
            month=month,
            day=0
        )

    @classmethod
    def expires_next_year(cls):
        current_time = time_now()
        return datetime(
            year=current_time.year + 1,
            month=1,
            day=0
        )

    @classmethod
    def expires_next_utc_day(cls):
        current_time = time_now().astimezone(timezone.utc)
        return (datetime(
            year=current_time.year,
            month=current_time.month,
            day=current_time.day,
            hour=0
        ) + timedelta(days=1)).replace(tzinfo=timezone.utc)

    entity_cls: Type[CacheEntity]   # can be override
    cache_alias: str
    # expiry_time: Union[int, datetime, timedelta, Callable]
    scope_prefix: str
    cache_control: str
    vary_header: Union[str, List[str]]
    vary_function: Callable[['Request'], str]

    def __init__(self, cache_alias: str = 'default',
                 scope_prefix: str = None,
                 # user can manually assign, and allow two cache instance have the same scope key
                 cache_control: str = None,
                 cache_response: bool = False,
                 etag_response: bool = False,
                 vary_header: Union[str, List[str]] = None,
                 vary_function: Callable[['Request'], str] = None,
                 expiry_time: Union[int, datetime, timedelta, Callable, None] = 0,
                 # normalizer, take the request and return the normalized result
                 max_entries: int = None,  # None means unlimited
                 max_entries_policy: str = OBSOLETE_LFU,
                 max_entries_tolerance: int = 0,
                 # if vary is specified, max_entries is relative to each variant
                 max_variants: int = None,
                 max_variants_policy: str = OBSOLETE_LFU,
                 max_variants_tolerance: int = 0,
                 trace_keys: bool = None,
                 default_timeout: Union[int, float, timedelta] = None,
                 entity_cls: Type[CacheEntity] = None,
                 document: str = None,
                 ):

        _locals = dict(locals())
        pop(_locals, 'self')
        super().__init__(**_locals)

        # from utilmeta.conf import config

        if expiry_time:
            if isinstance(expiry_time, (classmethod, staticmethod)):
                expiry_time = expiry_time.__func__
            assert isinstance(expiry_time, (int, float, datetime, timedelta)) or callable(expiry_time), \
                f'Invalid Cache expiry_time: {expiry_time}, must be instance of int/datetime/timedelta or a callable'
            if callable(expiry_time):
                expiry_time = self.function_parser_cls.apply_for(expiry_time)

        self.cache_control: Optional[str] = cache_control  # response cache control
        self.cache_response = cache_response
        self.etag_response = etag_response

        if vary_function:
            if not vary_header:
                if vary_function in (self.vary_user, self.vary_session):
                    # default function: vary to cookie
                    vary_header = self.VARY_COOKIE
                else:
                    warnings.warn(f'Cache with vary_function ({vary_function}) should specify a vary_header'
                                  f' to generate response["Vary"] header, like use vary_header="Cookie" '
                                  f'when you vary to user_id / session_id, because it is derived from cookie')

            assert callable(vary_function), f'Cache.vary_function must be a callable, got {vary_function}'
            # if config.preference.validate_request_functions:
            from utilmeta.core.request import Request
            _res = vary_function(Request())

        self.vary_header = vary_header
        self.vary_function = vary_function

        if not self.varied and self.max_variants:
            raise ValueError(f'Cache with max_variants: {self.max_variants} got no vary_header or vary_function')

        # private properties
        self._expiry_time = expiry_time

        # runtime properties
        self._max_age = None
        self._max_stale = None
        self._stale = False
        self._max_fresh = None
        self._expiry_datetime = None    # runtime
        self._if_modified_since: Optional[datetime] = None
        self._if_none_match: Optional[str] = None
        self._if_unmodified_since: Optional[datetime] = None
        self._if_match: Optional[str] = None
        self._cache_control: Optional[str] = None  # request cache control
        self._etag: Optional[str] = None
        self._last_modified: Optional[datetime] = None
        self._variant = None
        self._response_key = None
        self._context_func = None

    @property
    def varied(self) -> bool:
        return bool(self.vary_function or self.vary_header)

    @property
    def variant(self) -> str:
        return self._variant

    def init_expiry(self, request: 'Request') -> Optional[datetime]:
        expiry = self._expiry_time
        if callable(expiry):
            expiry = expiry(request)
        if expiry == 0:
            self._expiry_datetime = self._max_age = None
            return
        elif expiry is None:
            # set to a forever cache
            self._expiry_datetime = time_now() + self.FOREVER_TIMEDELTA
            self._max_age = int(self.FOREVER_TIMEDELTA.total_seconds())
            return
        if isinstance(expiry, date):
            expiry = datetime(year=expiry.year, month=expiry.month, day=expiry.day)
        if isinstance(expiry, datetime):
            self._expiry_datetime = expiry
            self._max_age = max(0, int((expiry - time_now()).total_seconds()))
        else:
            self._max_age = int(get_interval(expiry))
            self._expiry_datetime = time_now() + timedelta(seconds=self._max_age)

    def set_expiry(self, expires: Union[datetime, timedelta, int, float]):
        if isinstance(expires, datetime):
            self._expiry_datetime = expires
            self._max_age = max(0, int((expires - time_now()).total_seconds()))
        else:
            inv = get_interval(expires, null=True)
            if inv:
                self._expiry_datetime = time_now() + timedelta(seconds=inv)
                self._max_age = int(inv)

    def get_variant(self, request: 'Request') -> Optional[str]:
        if self.vary_function:
            # try not to contains sensitive data in vary_function results
            key = self.vary_function(request)
            # any not-null value will be treat as str
            if key is not None:
                return str(key)
        elif self.vary_header:
            header = request.headers.get(self.vary_header)
            if header is not None:
                return fast_digest(header)
        return None

    @classmethod
    def etag_function(cls, value):
        # can be inherit
        from utilmeta.utils import etag
        return etag(value)

    @property
    def has_entries(self):
        return self.max_entries != 0

    @property
    def no_store(self):
        """
        If request user send a Cache-Control: no-store
        we treat is as we don't store the response into cache
        event if max_entries is not 0 and not full
        but run the function and give the un-cached response
        """
        return self.request_cache_control == self.NO_STORE or not self.has_entries

    @property
    def no_cache(self):
        """
        If request user send a Cache-Control: no-cache
        we treat is as we don't use response in the cache,
        but run the function and get the un-cached response
        we may store it to cache if max_entries is not 0 and not full (unlike no-store)
        """
        return self.request_cache_control in (self.NO_CACHE, self.NO_STORE) or not self.has_entries

    @property
    def last_modified(self):
        return self._last_modified

    @last_modified.setter
    def last_modified(self, val):
        if val is None:
            return
        self._last_modified = type_transform(val, datetime)

    @property
    def etag(self):
        return self._etag

    @etag.setter
    def etag(self, val):
        self._etag = self.etag_function(val)

    def check_modified(self, last_modified: Union[datetime, int, float, str] = None,
                       resource=None, etag: str = None):
        if last_modified:
            self.last_modified = last_modified
        if etag or resource:
            self.etag = etag or resource

        if self.etag and self._if_none_match:
            if self.etag == self._if_none_match:
                raise exc.NotModified

        if self.last_modified and self._if_modified_since:
            if self.last_modified > self._if_modified_since:
                raise exc.NotModified

        return False

    def check_precondition(self, last_modified: Union[datetime, int, float, str] = None,
                           resource=None, etag: str = None):
        if not self._if_unmodified_since and not self._if_match:
            raise exc.PreconditionRequired(f'Request should provide precondition headers like '
                                           f'{Header.IF_MATCH} or {Header.IF_UNMODIFIED_SINCE}')

        if last_modified:
            self.last_modified = last_modified
        if etag or resource:
            self.etag = etag or resource

        if self.etag and self._if_match:
            if self.etag != self._if_match:
                raise exc.PreconditionFailed(f'Resource is modified: not match {self._if_match}')
        if self.last_modified and self._if_unmodified_since:
            if self.last_modified > self._if_unmodified_since:
                raise exc.PreconditionFailed(f'Resource has been modified since {self._if_unmodified_since}')

        return True

    @property
    def max_age(self):
        return self._max_age

    @max_age.setter
    def max_age(self, age: Union[timedelta, int, float]):
        age = get_interval(age, null=True)
        if age is not None:
            age = int(age)
        self._max_age = age

    @property
    def request_cache_control(self):
        return self._cache_control

    @property
    def response_cache_control(self):
        if self.cache_control:
            return self.cache_control
        if self.etag or self.last_modified:
            return self.NO_CACHE
        max_age = self.max_age
        if max_age:
            return f'{self.MAX_AGE}={max_age}'
        return None

    @response_cache_control.setter
    def response_cache_control(self, val):
        self.cache_control = val

    @property
    def if_modified_since(self):
        return self._if_modified_since

    @property
    def if_none_match(self):
        return self._if_none_match

    @property
    def if_match(self):
        return self._if_match

    @property
    def if_unmodified_since(self):
        return self._if_unmodified_since

    @property
    def headers(self) -> dict:
        return {k: v for k, v in {
            Header.ETAG: self.etag,
            Header.LAST_MODIFIED: http_time(self.last_modified),
            Header.CACHE_CONTROL: self.response_cache_control,
            Header.EXPIRES: http_time(self.expiry_datetime),
            Header.VARY: self.vary_header
        }.items() if v}

    @property
    def expiry_datetime(self) -> datetime:
        return self._expiry_datetime

    @expiry_datetime.setter
    def expiry_datetime(self, dt: datetime):
        self._expiry_datetime = type_transform(dt, datetime)

    def make_from_params(self, result, **func_params):
        if not self._context_func:
            warnings.warn('Cache: no context func is set')
            return
        dumped_key = f'{self._context_func.__name__}(%s)' % self.dump_kwargs(**func_params)
        # use func.__name__ cause when cache is define in API and not in Unit
        # __ref__ will not contains func name
        key = self.encode(dumped_key, ':')
        return self.make_response(result, response_key=key)

    def make_response(self, result, response_key=None):
        if result is None:
            # do not deal with None, no store, no check
            return None

        from django.http.response import HttpResponseBase

        if hasattr(result, '__next__'):
            return result

        if isinstance(result, HttpResponseBase):
            if result.status_code < 200 or result.status_code >= 300:
                # consider it's not a valid response to operate or store
                return result
            etag = result.headers.get(Header.ETAG)
            last_modified = result.headers.get(Header.LAST_MODIFIED)
            vary_header = result.headers.get(Header.VARY)
            if etag:
                self.etag = etag
            if last_modified:
                self.last_modified = last_modified
            if vary_header:
                if vary_header != self.vary_header:
                    self.vary_header = vary_header
                    # if not self.vary_function:
                    #     self._variant = self.get_variant()
            # do not set headers here, we will set headers in API/Module's __call__

        if self.etag_response and not self.etag:
            self.etag = self.etag_function(result)

        self.check_modified()
        # there are 2 cases
        # 1. developer set self.cache.etag/last_modified in the function, but not taking the modify check
        #    we will check it here and raise exc.NotModified if it does
        # 2. response provide it's own Etag/Last-Modified (like Media.stream will set Last-Modified)
        #    we will capture and check it here

        if response_key is None:
            response_key = self._response_key

        if self.cache_response and not self.no_store and response_key:
            self.set(response_key, result)
        return result

    @classmethod
    def _normalize_func_kwargs(cls, func, /, *args, **kwargs): # noqa
        if not args:
            return kwargs
        import inspect
        try:
            # make all args kwargs with it's arg name
            params = inspect.getcallargs(func, *args, **kwargs)
        except TypeError:
            return kwargs
        for omit in cls.OMIT_ARG_NAMES:
            # try to omit these param instead of using first_reserve
            # this is a trade-off and can consider as a convention
            # that when you declare a param named self / cls / mcs
            # it will not count into the cached result
            # (for the record, count it in will bring memory ID to the cache key)
            # (which will not be valid in another process / instance
            pop(params, omit)
        # private params (startswith "_") must count into cache
        # because if public params are same and private params are not
        # it will not tell the difference
        # for p in list(params):
        #     if p.startswith('_'):
        #         # consider the _ prefix param doesn't count to the kwargs
        #         pop(params, p)
        return params

    def encode(self, key: VAL, _con: str = '-', _variant=None):
        return super().encode(key, _con, _variant=_variant or self._variant)

    def decode(self, key: VAL, _variant=None):
        return super().decode(key, _variant=_variant or self._variant)

    def __call__(self, func: Callable, /, *args, **kwargs):  # noqa
        """
        This method is used for cache common function or API function
        when api_cache=True Unit will auto wrap partial(util.cache, executor) to call this method
        this method will also apply etag/last-modified assign and not_modified check
        !!it should call when the result is directly return!!
        eg:

        @api.get(cache=Cache(client_cache=True))
        def md(self, name: str, version: str, lang: str):
            path = self.media.get(f'{lang}/{version}/{name}.md')
            self.cache.last_modified = os.path.getmtime(path)
            return self.cache(render, path)

        because the result maybe a HttpResponse(status=304), so use it as a middle value will cause exception
        if you just want to cache a function with Cache
        use self.cache.apply(func, *args, **kwargs) or @api.cache to decorate the target function
        """
        assert callable(func), f'Cache.apply must apply to a callable function, got {func}'
        self.check_modified()
        key = None
        self._context_func = func
        if self.cache_response and not self.no_cache:
            params = self._normalize_func_kwargs(func, *args, **kwargs)
            dumped_key = f'{func.__name__}(%s)' % self.dump_kwargs(**params)
            # use func.__name__ cause when cache is define in API and not in Unit
            # __ref__ will not contains func name
            key = self.encode(dumped_key, ':')
            if not self._response_key:
                self._response_key = key
            # use another connector
            result = self.get(key)
            if result is not None:
                return result
        return self.make_response(func(*args, **kwargs), response_key=key)

    def make_cache(self, request):
        cache = self.__class__(**self.__spec_kwargs__)
        cache.__ref__ = self.__ref__

        # keep in the same scope
        from utilmeta.core.request import Request
        assert isinstance(request, Request), f'Invalid request: {request}, must be Request object'
        headers = request.headers
        modified_since = headers.get(Header.IF_MODIFIED_SINCE)
        unmodified_since = headers.get(Header.IF_UNMODIFIED_SINCE)
        if modified_since:
            try:
                cache._if_modified_since = type_transform(modified_since, datetime)
            except COMMON_ERRORS as e:
                warnings.warn(f'Cache: transform {Header.IF_MODIFIED_SINCE} failed with: {e}')
        if unmodified_since:
            try:
                cache._if_unmodified_since = type_transform(unmodified_since, datetime)
            except COMMON_ERRORS as e:
                warnings.warn(f'Cache: transform {Header.IF_UNMODIFIED_SINCE} failed with: {e}')
        cache._if_none_match = headers.get(Header.IF_NONE_MATCH)
        cache._if_match = headers.get(Header.IF_MATCH)
        cache._variant = cache.get_variant(request)
        cache._cache_control = headers.get(Header.CACHE_CONTROL)
        if cache._cache_control:
            for derivative in [v.strip() for v in cache._cache_control.split(',')]:
                if derivative.startswith(self.MAX_FRESH):
                    cache._max_fresh = int(derivative.split('=')[1])
                elif derivative.startswith(self.MAX_STALE):
                    if '=' in derivative:
                        cache._max_stale = int(derivative.split('=')[1])
                    else:
                        cache._stale = True
        cache.init_expiry(request)
        return cache


from utilmeta.core.api.base import API, process_response, setup_instance
from utilmeta.core.response import Response


@setup_instance.hook(API)
def setup_instance_for_cache(cache: ServerCache, api: API, __attname__: str):
    setattr(api, __attname__, cache.make_cache(api.request))


@process_response.hook(API)
def process_response_for_cache(cache: ServerCache, response: Response):
    response.update_headers(**cache.headers)
