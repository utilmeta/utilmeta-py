from .base import BaseCacheInterface
from .entity import CacheEntity
from utilmeta.core.request import Request
from utilmeta.core.response import Response
from utilmeta.utils import multi, time_now, Header, pop
from utype.types import *
from utype import Schema, Options, Field
from functools import cached_property


__all__ = ["ClientCache"]

NO_CACHE = "no-cache"
NO_STORE = "no-store"
NO_TRANSFORM = "no-transform"
PUBLIC = "public"
IMMUTABLE = "immutable"
MAX_AGE = "max-age"
MAX_STALE = "max-stale"
MAX_FRESH = "max-fresh"
PRIVATE = "private"
MUST_REVALIDATE = "must-revalidate"


class CacheHeaderSchema(Schema):
    __options__ = Options(
        case_insensitive=True, ignore_required=True, force_default=None
    )

    cache_control: str = Field(alias_from=[Header.CACHE_CONTROL, Header.PRAGMA])
    # RESPONSE headers
    expires: datetime
    date: datetime
    age: datetime
    last_modified: datetime = Field(alias=Header.LAST_MODIFIED)
    etag: str
    vary: str
    # ---
    # REQUEST headers
    if_modified_since: datetime = Field(alias=Header.IF_MODIFIED_SINCE)
    if_unmodified_since: datetime = Field(alias=Header.IF_UNMODIFIED_SINCE)
    if_none_match: str = Field(alias=Header.IF_NONE_MATCH)
    if_match: str = Field(alias=Header.IF_MATCH)

    @cached_property
    def cache_control_derivatives(self):
        if not self.cache_control:
            return []
        return [v.strip() for v in self.cache_control.split(",")]

    @property
    def immutable(self):
        return IMMUTABLE in self.cache_control_derivatives

    @property
    def public(self):
        return PUBLIC in self.cache_control_derivatives

    @property
    def private(self):
        return PRIVATE in self.cache_control_derivatives

    @property
    def no_cache(self):
        # no-cache and no-store all means do not attempt to read from cached response
        return (
            NO_CACHE in self.cache_control_derivatives
            or NO_STORE in self.cache_control_derivatives
        )

    @property
    def no_store(self):
        if self.vary == "*":
            # vary for all, this response is not cache-able
            return True
        if (
            not self.cache_control
            and not self.expires
            and not self.etag
            and not self.last_modified
        ):
            # no cache headers is presenting
            return True
        return NO_STORE in self.cache_control_derivatives

    @property
    def must_revalidate(self):
        return MUST_REVALIDATE in self.cache_control_derivatives

    @property
    def max_age(self) -> Optional[int]:
        for d in self.cache_control_derivatives:
            if d.startswith(MAX_AGE):
                return int(d.split("=")[1].strip())
        if self.expires:
            # fallback to expires
            return max(
                0, int((self.expires - (self.date or time_now())).total_seconds())
            )
        return None

    @property
    def vary_headers(self):
        if not self.vary:
            return []
        return [v.strip() for v in self.vary.split(",")]

    @property
    def max_stale(self) -> Optional[int]:
        for d in self.cache_control_derivatives:
            if d.startswith(MAX_STALE):
                if "=" not in d:
                    return -1
                return int(d.split("=")[1].strip())
        return None

    @property
    def max_fresh(self) -> Optional[int]:
        for d in self.cache_control_derivatives:
            if d.startswith(MAX_FRESH):
                return int(d.split("=")[1].strip())
        return None


class ClientCache(BaseCacheInterface):
    # could use a refer: https://docs.scrapy.org/en/latest/_modules/scrapy/extensions/httpcache.html#RFC2616Policy
    """
    Cache Client Utility that implements Web standard http cache
    * 304 Not Modified
    * Cache-Control
    * Expires
    * Last-Modified  ~ If-Modified-Since
    * Etag           ~ If-None-Match
    """

    def __init__(
        self,
        cache_alias: str = "default",
        scope_prefix: str = None,
        services_sharing: bool = False,
        # enable this param will make cache key without service_prefix
        # so that every service using this cache can access to the cached response
        entity_cls: Type[CacheEntity] = None,
        disable_304: bool = False,
        disable_etag: bool = False,
        disable_last_modified: bool = False,
        disable_vary: bool = False,
        max_entries: int = 0,
        max_entries_policy: str = BaseCacheInterface.OBSOLETE_LFU,
        max_entries_tolerance: int = 0,
        trace_keys: bool = True,
        default_request_cache_control: str = None,
        default_response_cache_control: str = None,
        default_timeout: int = None,
        excluded_statuses: List[int] = None,
        included_statuses: List[int] = None,
        included_methods: List[str] = ("GET", "HEAD"),
        excluded_hosts: Union[
            str, List[str]
        ] = None,  # do not cache responses from these hosts
        included_hosts: Union[
            str, List[str]
        ] = None,  # only cache responses from these hosts
    ):
        # use max hosts as max_variants to be part of locals()
        _locals = dict(locals())
        pop(_locals, "self")
        super().__init__(**_locals)

        self.disable_304 = disable_304
        self.disable_etag = disable_etag
        self.disable_last_modified = disable_last_modified
        self.disable_vary = disable_vary
        self.excluded_statuses = excluded_statuses
        self.included_statuses = included_statuses
        self.included_methods = [m.upper() for m in included_methods]
        if not multi(excluded_hosts):
            excluded_hosts = [excluded_hosts]
        if not multi(included_hosts):
            included_hosts = [included_hosts]
        self.excluded_hosts = excluded_hosts
        self.included_hosts = included_hosts
        self.services_sharing = services_sharing
        if self.services_sharing:
            self._service_prefix = None

    @property
    def varied(self) -> bool:
        # vary by host
        return True

    @classmethod
    def vary_function(cls, request: Request):
        # can be inherit and modify
        return request.hostname

    def bypass_request(self, request: Request):
        if not request:
            return True
        if request.method not in self.included_methods:
            return True
        if self.included_hosts:
            if request.hostname not in self.included_hosts:
                return True
        elif self.excluded_hosts:
            if request.hostname in self.excluded_hosts:
                return True
        return False

    def bypass_response(self, response: "Response"):
        if self.bypass_request(response.request):
            # url not set, cannot cache
            return True
        if self.included_statuses:
            if response.status not in self.included_statuses:
                return True
        elif self.excluded_statuses:
            if response.status in self.excluded_statuses:
                return True
        if response.status == 304:
            # treat 304 specially
            if self.disable_304:
                return True
            return False
        if response.status < 200 or response.status > 300:
            return True
        return False

    def process_request(self, request: Request):
        if self.bypass_request(request):
            return request

        headers = CacheHeaderSchema(request.headers)
        if headers.no_cache:
            return request

        cached_response = self.get_cached_response(request)

        if not cached_response:
            return request

        cached_headers = CacheHeaderSchema(cached_response.headers)

        if not self.disable_vary:
            for name in cached_headers.vary_headers:
                original_header = cached_response.request.headers.get(name)
                current_header = request.headers.get(name)
                # even if header is None, we will include that into the values
                # because if header turn None to a existing value
                # then it's consider different
                if original_header != current_header:
                    # vary cached
                    return request

        if cached_headers.expires:
            # if we have expires here
            # we can check the freshness more accurately
            # (rather than depending on the cache's timeout)
            if request.time >= cached_headers.expires:
                return request

        if cached_headers.max_age:
            # in this case we say that the response is still valid
            # (because timeout is still not pass)
            return cached_response

        # here we deal with conditional cache queries with etag / last-modified
        if cached_headers.etag:
            if not headers.if_none_match:
                request.headers.setdefault(Header.IF_NONE_MATCH, cached_headers.etag)
                # modify the If-None-Match header
        if cached_headers.last_modified:
            if not headers.if_modified_since:
                request.headers.setdefault(
                    Header.IF_MODIFIED_SINCE, cached_headers.last_modified
                )
                # modify the If-Modified-Since header
        return request

    def get_cached_response(self, request: Request) -> Optional["Response"]:
        resp_key = self.get_response_key(request)
        if not resp_key:
            return None
        entity = self.get_entity(variant=self.vary_function(request))
        cached_response = entity.get(resp_key, single=True)
        if isinstance(cached_response, Response):
            if not cached_response.data:
                cached_response.data = cached_response.result
            cached_response.cached = True
            cached_response.request = request
            return cached_response
        return None

    def get_response_key(self, request: Request):
        if not request:
            return None
        # not using vary values as cache key
        # us vary as a validation (to validate whether the cache is still fresh)
        return self.encode(
            key=f"{request.method.lower()}:{request.encoded_path}",
            _variant=self.vary_function(request),
        )

    def process_response(self, response: "Response"):  # hook
        if self.bypass_response(response):
            # url not set, cannot cache
            return response

        if response.status == 304:
            # handle it specially
            cached_response = self.get_cached_response(response.request)
            if cached_response:
                cached_response.push_response_stack(response)
                return cached_response
            return response

        # by default we only cache status within 2xx
        cache_headers = CacheHeaderSchema(response.headers)
        if cache_headers.no_store:
            return response
            # no-cache means we can cache
            # but each time the resource is being asked we should go to the original server
            # to ask whether the resource is stale
            # if server give a 304, we can use the local cache

        max_age = cache_headers.max_age
        resp_key = self.get_response_key(response.request)

        if not resp_key:
            return response

        entity = self.get_entity(variant=self.vary_function(response.request))

        if max_age == 0:
            if cache_headers.must_revalidate:
                # do not delete cache when detect this derivative
                return response

            # delete response if it's expired
            entity.delete(resp_key)
            return response

        if max_age is None:
            # max_age=None is consider timeout=0
            # we use default timeout here
            timeout = self.default_timeout
            # case 1: response indicate Cache-Control: public/must-revalidate without max-age and Expires specified
            # case 2: etag / last-modified specified, use default timeout
            # if default timeout is 0, means we don't store such response
        else:
            timeout = max_age

        if timeout == 0:
            # consider the resource is expired
            return response

        # remove redundant properties when settings response to increase space efficiency
        raw = response.raw_response
        data = response.data
        request = response.request
        if response.data == response.result:
            response.data = None
        response.raw_response = None
        response.request = None
        # ---

        entity.set(key=resp_key, val=response, timeout=timeout)
        response.data = data
        response.raw_response = raw
        response.request = request
        return response
