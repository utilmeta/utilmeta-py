import inspect

from utype.types import *
from utilmeta.utils import multi, get_origin, Header, distinct_add
from utilmeta.utils import exceptions as exc
from utilmeta.core.request import Request
from utilmeta.core.request import var
from utilmeta.core.response import Response
from .base import APIPlugin


class CORSPlugin(APIPlugin):
    DEFAULT_ALLOW_HEADERS = ('content-type', 'content-length', 'accept', 'origin', 'user-agent')
    EXCLUDED_STATUS = (502, 503, 504)

    def __init__(self,
                 allow_origin: Union[List[str], str] = None,
                 cors_max_age: Union[int, timedelta, float] = None,
                 allow_headers: List[str] = (),
                 allow_errors: List[Type[Exception]] = (Exception,),
                 expose_headers: List[str] = None,
                 csrf_exempt: bool = None,
                 exclude_statuses: List[int] = EXCLUDED_STATUS,
                 gen_csrf_token: bool = None,
                 options_200: bool = True,
                 override: bool = False,
                 ):
        super().__init__(locals())

        self.csrf_exempt = csrf_exempt

        if allow_origin:
            if isinstance(allow_origin, str):
                allow_origin = [allow_origin]
            elif not multi(allow_origin):
                raise TypeError(f'Request allow_origin must be None, "*" or a origin str / str list')

        if '*' in allow_origin:
            self.allow_origins = ['*']
        else:
            self.allow_origins = [get_origin(origin) for origin in allow_origin if origin]

        if self.allow_all_origin:
            if self.csrf_exempt is None:
                # cross domain. no csrf check
                self.csrf_exempt = True

        if allow_headers is None or not allow_headers:
            allow_headers = []
        else:
            if not multi(allow_headers):
                allow_headers = [allow_headers]
            allow_headers = [str(h).lower() for h in allow_headers]

        if multi(allow_headers):
            distinct_add(allow_headers, self.DEFAULT_ALLOW_HEADERS)

        if allow_errors and not multi(allow_errors):
            allow_errors = [allow_errors]

        self.allow_errors = tuple([e for e in allow_errors if isinstance(e, type) and issubclass(e, Exception)]) \
            if allow_errors else None
        self.allow_headers: list = allow_headers or []
        self.cors_max_age = cors_max_age
        self.expose_headers = expose_headers
        self.gen_csrf_token = gen_csrf_token
        self.exclude_statuses = exclude_statuses
        self.options_200 = options_200
        self.override = override

    @property
    def allow_all_origin(self):
        return self.allow_origins and '*' in self.allow_origins

    @property
    def allow_all_headers(self):
        return self.allow_headers and '*' in self.allow_headers

    def __call__(self, func, *args, **kwargs):
        from ..base import API
        if inspect.isclass(func) and issubclass(func, API):
            if not hasattr(func, 'response'):
                from utilmeta.core.response import Response
                func.response = Response
        return super().__call__(func, *args, **kwargs)

    def process_request(self, request: Request):
        from utilmeta import service
        if request.origin != service.origin:
            # origin cross settings is above all other request control settings
            # so that when request error occur, the cross-origin settings can take effect
            # so that client see a valid error message instead of a CORS error
            if not self.allow_origins:
                raise exc.PermissionDenied(f'Invalid request origin: {request.origin}')
            else:
                if not self.allow_all_origin:
                    if request.origin not in self.allow_origins:
                        raise exc.PermissionDenied(f'Invalid request origin: {request.origin}')

        if self.gen_csrf_token:
            request.adaptor.gen_csrf_token()
        elif not self.csrf_exempt:
            # only check csrf for from_api requests
            if not request.adaptor.check_csrf_token():
                raise exc.PermissionDenied(f'CSRF token missing or incorrect')

    def cors_required(self, request: Request) -> bool:
        """
        Need to set Access-Control-Allow-xxx headers for response
        :return:
        """
        # error default, so when error occur, CORS headers cam also be set
        if not request:
            return False
        if request.is_options or self.allow_all_origin:
            return True
        from utilmeta import service
        if request.origin != service.origin:
            return True
        return self.allow_origins and request.origin not in self.allow_origins

    def process_response(self, response: Response):
        if not isinstance(response, Response):
            return response
        request: Request = response.request
        if not request:
            return response
        if request.is_options and self.options_200:
            response.status = 200
        if response.status in self.exclude_statuses:
            return response
        if Header.ALLOW_ORIGIN in response:
            # already processed
            if not self.override:
                return response
        if self.cors_required(request):
            response.update_headers(**{
                Header.ALLOW_ORIGIN: request.origin or '*',
                Header.ALLOW_CREDENTIALS: 'true',
                Header.ALLOW_METHODS: ','.join(set([m.upper() for m in var.allow_methods.getter(request)])),
            })
            if request.is_options:
                if self.allow_all_headers:
                    response.set_header(Header.ALLOW_HEADERS, '*')
                else:
                    # request_headers = [h.strip().lower() for h in
                    #                    request.headers.get(Header.OPTIONS_HEADERS, '').split(',')]
                    allow_headers = list(self.allow_headers or [])
                    allow_headers.extend([h.lower() for h in var.allow_headers.getter(request)])
                    if allow_headers:
                        response.set_header(Header.ALLOW_HEADERS, ','.join(allow_headers))

            if self.expose_headers:
                response.set_header(Header.EXPOSE_HEADERS, ','.join(set([h.lower() for h in self.expose_headers])))
            if self.cors_max_age:
                response.set_header(Header.ACCESS_MAX_AGE, self.cors_max_age)
        return response

    def handle_error(self, error, api=None):
        if not self.allow_errors:
            return
        if not isinstance(error.exception, self.allow_errors):
            return
        # if error is uncaught
        if api:
            make_response = getattr(api, '_make_response', None)
            # this is a rather ugly hack, maybe we will figure out something nicer or universal
            # because we need to postpone the response process
            if callable(make_response):
                from functools import wraps

                @wraps(make_response)
                def _make_response(response, force: bool = False):
                    return self.process_response(make_response(response, force))
                api._make_response = _make_response
                return
                # process with error hooks
                # response = api._make_response(api._handle_error(error))
                # if error is raised here
        return self.process_response((getattr(api, 'response', None) or Response)(
            error=error,
            request=error.request
        ))
