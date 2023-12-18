from .base import RequestAdaptor
from django.http.request import HttpRequest
from django.middleware.csrf import CsrfViewMiddleware, get_token
from utilmeta.utils import parse_query_dict, cached_property, Header, LOCAL_IP
from ipaddress import ip_address
from utilmeta.core.file.backends.django import DjangoFileAdaptor
from utilmeta.core.file.base import File


def get_request_ip(meta: dict):
    ips = [*meta.get(Header.FORWARDED_FOR, '').replace(' ', '').split(','),
           meta.get(Header.REMOTE_ADDR)]
    if '' in ips:
        ips.remove('')
    if LOCAL_IP in ips:
        ips.remove(LOCAL_IP)
    for ip in ips:
        try:
            return ip_address(ip)
        except ValueError:
            continue
    return ip_address(LOCAL_IP)


class DjangoRequestAdaptor(RequestAdaptor):
    file_adaptor_cls = DjangoFileAdaptor

    def gen_csrf_token(self):
        return get_token(self.request)

    def check_csrf_token(self) -> bool:
        err_resp = CsrfViewMiddleware(lambda *_: None).process_view(self.request, None, None, None)
        return err_resp is None

    @property
    def request_method(self):
        return self.request.method

    @cached_property
    def url(self):
        if hasattr(self.request, 'get_raw_uri'):
            return self.request.get_raw_uri()
        self.request.build_absolute_uri()

    @cached_property
    def address(self):
        return get_request_ip(self.request.META)

    @classmethod
    def load_form_data(cls, request):
        m = request.method
        load_call = getattr(request, '_load_post_and_files')
        if m in ('PUT', 'PATCH'):
            if hasattr(request, '_post'):
                delattr(request, '_post')
                delattr(request, '_files')
            try:
                request.method = 'POST'
                load_call()
                request.method = m
            except AttributeError:
                request.META['REQUEST_METHOD'] = 'POST'
                load_call()
                request.META['REQUEST_METHOD'] = m

    def get_form(self):
        self.load_form_data(self.request)
        data = parse_query_dict(self.request.POST)
        parsed_files = {}
        for key, files in self.request.FILES.items():
            parsed_files[key] = [File(self.file_adaptor_cls(file)) for file in files]
        data.update(parsed_files)
        return data

    async def async_load(self):
        raise NotImplementedError

    async def async_read(self):
        # from django.core.handlers.asgi import ASGIRequest
        # if isinstance(self.request, ASGIRequest):
        #     return self.request.read()
        return self.body
        # not actually "async", but could be used from async server

    @cached_property
    def encoded_path(self):
        try:
            return self.request.get_full_path()
        except AttributeError:
            from django.utils.encoding import escape_uri_path
            # RFC 3986 requires query string arguments to be in the ASCII range.
            # Rather than crash if this doesn't happen, we encode defensively.
            path = escape_uri_path(self.request.path)
            qs = self.request.META.get('QUERY_STRING', '')
            if qs:
                path += '?' + qs
            return path

    @property
    def body(self):
        return self.request.body

    @property
    def headers(self):
        return self.request.headers

    @property
    def scheme(self):
        return self.request.scheme

    @property
    def query_string(self):
        return self.request.META.get('QUERY_STRING', '')

    @property
    def query_params(self):
        return parse_query_dict(self.request.GET)

    @property
    def cookies(self):
        return self.request.COOKIES

    def __init__(self, request: HttpRequest, route: str = None, *args, **kwargs):
        super().__init__(request, route, *args, **kwargs)
        self.request = request
