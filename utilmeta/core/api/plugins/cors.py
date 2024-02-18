from utype.types import *
from utilmeta.utils import multi, get_origin, Header
from utilmeta.utils import exceptions as exc
from utilmeta.utils.plugin import Plugin
from utilmeta.core.request import Request
from utilmeta.core.request import var
from utilmeta.core.response import Response


class CORSPlugin(Plugin):
    DEFAULT_ALLOW_HEADERS = ('content-Type', 'content-length', 'accept', 'origin', 'user-Agent')
    EXCLUDED_STATUS = (502, 503, 504)

    def __init__(self,
                 allow_origin: Union[List[str], str] = None,
                 cors_max_age: Union[int, timedelta, float] = None,
                 allow_headers: List[str] = (),
                 expose_headers: List[str] = None,
                 csrf_exempt: bool = None,
                 exclude_statuses: List[int] = EXCLUDED_STATUS,
                 gen_csrf_token: bool = None):
        super().__init__(locals())

        self.csrf_exempt = csrf_exempt

        if allow_origin:
            if isinstance(allow_origin, str):
                if allow_origin != '*':
                    allow_origin = [allow_origin]
                else:
                    if self.csrf_exempt is None:
                        # cross domain. no csrf check
                        self.csrf_exempt = True
            elif not multi(allow_origin):
                raise TypeError(f'Request allow_origin must be None, "*" or a origin str / str list')

        if multi(allow_origin):
            self.allow_origins = [get_origin(origin) for origin in allow_origin]
        else:
            self.allow_origins = allow_origin

        if allow_headers is None or not allow_headers:
            allow_headers = []
        elif allow_headers != '*':
            if not multi(allow_headers):
                allow_headers = [allow_headers]
            allow_headers = [str(h).lower() for h in allow_headers]

        if multi(allow_headers):
            for dh in self.DEFAULT_ALLOW_HEADERS:
                if dh not in allow_headers:
                    allow_headers.append(dh)

        self.allow_origin = allow_origin
        self.cors_max_age = cors_max_age
        self.allow_headers = allow_headers or []
        self.expose_headers = expose_headers
        self.gen_csrf_token = gen_csrf_token
        self.exclude_statuses = exclude_statuses

    def process_request(self, request: Request, api=None):
        from utilmeta import service
        if request.origin != service.origin:
            # origin cross settings is above all other request control settings
            # so that when request error occur, the cross-origin settings can take effect
            # so that client see a valid error message instead of a CORS error
            if self.allow_origins is None:
                raise exc.PermissionDenied(f'Invalid request origin: {request.origin}')
            else:
                if self.allow_origins != '*':
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
        if request.is_options or self.allow_origins == '*':
            return True
        from utilmeta import service
        if request.origin != service.origin:
            return True
        return self.allow_origins and request.origin not in self.allow_origins

    def process_response(self, response: Response, api=None):
        if not isinstance(response, Response):
            return response
        request: Request = response.request
        if not request:
            return response
        if Header.ALLOW_ORIGIN in response:
            # already processed
            return response
        if response.status in self.exclude_statuses:
            return response
        if self.cors_required(request):
            response.update_headers(**{
                Header.ALLOW_ORIGIN: request.origin or '*',
                Header.ALLOW_CREDENTIALS: 'true',
                Header.ALLOW_METHODS: ','.join(set([m.upper() for m in var.allow_methods.getter(request)])),
            })
            if request.is_options:
                if self.allow_headers == '*':
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

    def handle_error(self, error, api):
        # if error is uncaught
        return getattr(api, 'response', Response)(error=error, request=api.request)
