import io
import json
from typing import Optional, Union, Dict
from .backends.base import RequestAdaptor
from http.cookies import SimpleCookie
from urllib.parse import urlsplit, urlencode, urlunsplit
from utilmeta.utils import Headers, pop, file_like, \
    RequestType, encode_multipart_form, json_dumps, multi,\
    parse_query_string, parse_query_dict
from collections.abc import Mapping
import mimetypes


class ClientRequest:
    def __init__(self,
                 method: str,
                 url: str,
                 query: dict = None,
                 data=None,
                 headers: Dict[str, str] = None):

        self._method = method
        self.headers = Headers(headers or {})
        cookie = SimpleCookie(self.headers.get('cookie', {}))
        self.cookies = {k: v.value for k, v in cookie.items()}

        self._data = data
        self.body: Optional[bytes] = None
        self._file = None
        self._form: Optional[dict] = None
        self._json: Union[dict, list, None] = None

        self._url = url or ''
        self._query = parse_query_dict(query or {})

        self.build_url()
        self.build_body()

    @property
    def method(self):
        return self._method

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, data):
        self._data = data
        self.build_body()

    @property
    def query(self):
        return self._query

    @query.setter
    def query(self, q):
        if isinstance(q, str):
            q = parse_query_string(q)
        elif isinstance(q, dict):
            q = parse_query_dict(q)
        else:
            return
        if not q:
            return
        self._query = q
        self.build_url()

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, url):
        self._url = str(url)
        self.build_url()

    def build_url(self):
        if not self._query:
            return
        url_parsed = urlsplit(self._url)
        url_query = parse_query_string(url_parsed.query) if url_parsed.query else {}
        url_query.update(self._query)
        self._url = urlunsplit((
            url_parsed.scheme,
            url_parsed.netloc,
            url_parsed.path,
            urlencode(url_query),
            url_parsed.fragment
        ))

    @property
    def route(self):
        return urlsplit(self.url).path.strip('/')

    @property
    def content_type(self) -> Optional[str]:
        return self.headers.get('content-type')

    @content_type.setter
    def content_type(self, t):
        self.headers['content-type'] = t

    @property
    def contains_files(self):
        if isinstance(self.data, dict):
            for key, val in self.data.items():
                if multi(val):
                    for v in val:
                        if file_like(v):
                            return True
                elif file_like(val):
                    return True
        return False

    def reset_files(self):
        if isinstance(self.data, dict):
            for key, val in self.data.items():
                if multi(val):
                    for v in val:
                        if file_like(v):
                            v.seek(0)
                elif file_like(val):
                    val.seek(0)

    @property
    def json(self):
        return self._json

    @property
    def form(self):
        return self._form

    @property
    def file(self):
        return self._file

    def build_body(self):
        if self.data is None:
            return

        pop(self.headers, 'content-length')
        # there are difference between JSON.stringify in js and json.dumps in python
        # while JSON.stringify leave not spaces and json.dumps leave space between a comma and next key
        # difference like {"a":1,"b":2} and {"a": 1, "b": 2}
        # so these different encode standard gives a different Content-Length
        # and reuse the original Content-Length may cause decode error on target server parsing the request body

        if isinstance(self.data, (bytes, io.BytesIO)):
            self.body = self.data

            if isinstance(self.body, io.BytesIO):
                self._file = self.body

            if self.content_type:
                if self.content_type.startswith(RequestType.JSON):
                    self._json = json.loads(self.data) if isinstance(self.data, bytes) else json.load(self.data)

                elif self.content_type.startswith(RequestType.FORM_URLENCODED):
                    qs = self.data
                    if isinstance(qs, io.BytesIO):
                        qs = qs.read()
                    self._form = parse_query_string(qs.decode())

        else:
            if self.content_type:
                if self.content_type.startswith(RequestType.FORM_DATA):
                    if isinstance(self.data, (dict, Mapping)):
                        self.body, self.content_type = encode_multipart_form(self.data)
                        self._form = self.data
                        self.reset_files()
                    else:
                        # should raise?
                        self.body = str(self.data).encode()

                elif self.content_type.startswith(RequestType.JSON):
                    if isinstance(self.data, (dict, Mapping)) or multi(self.data):
                        self.body = json_dumps(self.data).encode()
                        self._json = self.data
                    else:
                        # should raise?
                        self.body = str(self.data).encode()

                elif self.content_type.startswith(RequestType.FORM_URLENCODED):
                    if isinstance(self.data, (dict, Mapping)) or multi(self.data):
                        self._form = dict(self.data)
                        self.body = urlencode(self._form).encode()
                    elif isinstance(self.data, str):
                        self.body = self.data.encode()
                        self._form = parse_query_string(self.data)
                    else:
                        self.body = str(self.data).encode()

                else:
                    if file_like(self.data):
                        self._file = self.data

                    self.body = str(self.data).encode()
            else:
                # guess by data type

                if isinstance(self.data, str):
                    self.body = self.data.encode()

                elif isinstance(self.data, (dict, Mapping)):
                    # check if there are file
                    if self.contains_files:
                        self.body, self.content_type = encode_multipart_form(self.data)
                        self._form = self.data
                        self.reset_files()
                    else:
                        self.content_type = RequestType.JSON
                        self.body = json_dumps(self.data).encode()
                        self._json = dict(self.data)

                elif multi(self.data):
                    self.content_type = RequestType.JSON
                    self.body = json_dumps(self.data).encode()
                    self._json = list(self.data)

                elif file_like(self.data):
                    name = getattr(self.data, 'name', None)
                    self.content_type = mimetypes.guess_type(name)[0] if name else RequestType.OCTET_STREAM
                    self.data.seek(0)
                    content = self.data.read()
                    if not isinstance(content, bytes):
                        content = str(content).encode()
                    self.body = content
                    self._file = self.data

                else:
                    self.body = str(self.data).encode()
                    self.content_type = RequestType.PLAIN


class ClientRequestAdaptor(RequestAdaptor):
    request: ClientRequest

    def __init__(self, request: ClientRequest, route: str = None, *args, **kwargs):
        super().__init__(request, route=route or request.route, *args, **kwargs)

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, ClientRequest)

    @property
    def address(self):
        from ipaddress import ip_address
        return ip_address('127.0.0.1')

    # @property
    # def content_type(self) -> Optional[str]:
    #     ct = super().content_type
    #     if ct:
    #         return ct
    #     if isinstance(self.request.data, (dict, list)):
    #         return 'application/json'
    #     return None

    @property
    def content_length(self) -> int:
        length = self.headers.get('content-length')
        if length is not None:
            return int(length or 0)
        if self.body:
            body = self.body
            if isinstance(body, bytes):
                return len(body)
            elif isinstance(body, io.BytesIO):
                length = len(body.read())
                body.seek(0)
                return length
        return 0

    @property
    def request_method(self) -> str:
        return self.request.method

    @property
    def url(self) -> str:
        return str(self.request.url)

    @property
    def cookies(self):
        return self.request.cookies

    @property
    def query_params(self):
        return self.request.query

    @property
    def query_string(self):
        return urlsplit(self.request.url).query

    @property
    def path(self):
        return urlsplit(self.request.url).path

    @property
    def scheme(self):
        return urlsplit(self.request.url).scheme or 'http'

    @property
    def headers(self):
        return self.request.headers

    def get_form(self):
        return self.request.form

    def get_json(self):
        return self.request.json

    def get_file(self):
        return self.request.file

    @property
    def body(self) -> bytes:
        return self.request.body

    @body.setter
    def body(self, data):
        self.request.data = data

    async def async_read(self):
        return self.request.body

    async def async_load(self):
        return self.get_content()
