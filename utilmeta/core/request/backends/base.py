from urllib.parse import urlsplit, urlunsplit
from typing import Optional
from utilmeta.utils import MetaMethod, CommonMethod, Header, \
    RequestType, cached_property, time_now, gen_key, parse_query_string
from utilmeta.utils import exceptions as exc
from utilmeta.utils import LOCAL_IP
from ipaddress import ip_address
from utilmeta.utils.adaptor import BaseAdaptor
import json
from collections.abc import Mapping


def get_request_ip(headers: Mapping):
    ips = [*headers.get('x-forwarded-for', '').replace(' ', '').split(','),
           headers.get('remote-addr')]
    if '' in ips:
        ips.remove('')
    if LOCAL_IP in ips:
        ips.remove(LOCAL_IP)
    for ip in ips:
        try:
            return ip_address(ip)
        except ValueError:
            continue
    return None


class RequestAdaptor(BaseAdaptor):
    file_adaptor_cls = None
    json_decoder_cls = json.JSONDecoder

    def __init__(self, request, route: str = None, *args, **kwargs):
        self.request = request
        self.route = str(route or '').strip('/')
        self.args = args
        self.kwargs = kwargs
        self.time = time_now()

        self._context = {}
        self._override_method = None
        self._override_route = None
        self._override_query = None
        self._override_data = None

        # self.logger = config.preference.logger_cls()  # root request context logger
        # self.json_decoder_cls = config.preference.json_decoder_cls
        # state during request processing
        # 1. data loaded
        # 2. user loaded

    def __contains__(self, item):
        return item in self._context

    def __getitem__(self, item):
        return self._context[item]

    def __setitem__(self, key, value):
        self._context[key] = value

    def get_context(self, key, default=None):
        return self._context.get(key, default)

    def update_context(self, **kwargs):
        return self._context.update(**kwargs)

    def delete_context(self, key: str):
        if key in self._context:
            self._context.pop(key)

    def in_context(self, key: str):
        return key in self._context

    def clear_context(self):
        self._context.clear()

    @classmethod
    def reconstruct(cls, adaptor: 'RequestAdaptor'):
        if isinstance(adaptor, cls):
            return adaptor.request
        raise NotImplementedError

    # example
    # POST https://sub.main.com:8080/api/users?query=a --body={} --headers={}

    def gen_csrf_token(self):
        raise NotImplementedError

    def check_csrf_token(self) -> bool:
        raise NotImplementedError

    @property
    def address(self):
        return get_request_ip(self.headers) or ip_address(LOCAL_IP)

    @property
    def method(self):
        if self._override_method:
            return self._override_method
        m = self.request_method.lower()
        if m == MetaMethod.HEAD:
            m = CommonMethod.GET
        elif m == MetaMethod.OPTIONS:
            m = self.headers.get(Header.OPTIONS_METHOD, m).lower()
        return m

    @method.setter
    def method(self, method: str):
        self._override_method = method

    @property
    def request_method(self) -> str:
        raise NotImplementedError

    @property
    def url(self):  # full url
        raise NotImplementedError

    @property
    def encoded_path(self):
        parsed = urlsplit(self.url)
        if parsed.query:
            return parsed.path + '?' + parsed.query
        return parsed.path

    @property
    def path(self):
        return urlsplit(self.url).path

    @property
    def hostname(self):
        return urlsplit(self.url).hostname

    @property
    def origin(self):
        origin_header = self.headers.get('origin')
        if origin_header:
            return origin_header
        s = urlsplit(self.url)
        return urlunsplit((s.scheme, s.netloc, '', '', ''))

    @property
    def scheme(self):
        return urlsplit(self.url).scheme

    @property
    def query_string(self):
        return urlsplit(self.url).query

    @property
    def query_params(self):
        return parse_query_string(self.query_string)

    @property
    def cookies(self):
        raise NotImplementedError

    @property
    def headers(self):
        raise NotImplementedError

    @cached_property
    def content_type(self) -> Optional[str]:
        ct = self.headers.get(Header.TYPE)
        if not ct:
            return
        ct = str(ct)
        if ';' in ct:
            return ct.split(';')[0].strip()
        return ct

    @property
    def content_length(self) -> int:
        return int(self.headers.get(Header.LENGTH) or 0)

    @property
    def json_type(self):
        content_type = self.content_type
        return content_type == RequestType.JSON

    @property
    def xml_type(self):
        content_type = self.content_type
        return content_type in (RequestType.XML, RequestType.APP_XML)

    @property
    def form_type(self):
        content_type = self.content_type
        if not content_type:
            return False
        return content_type in (RequestType.FORM_URLENCODED, RequestType.FORM_DATA)

    @property
    def file_type(self):
        content_type = self.content_type
        maj, sec = content_type.split('/')
        if maj in ('video', 'audio', 'image'):
            return True
        if sec == 'octet-stream':
            return True
        return False

    @property
    def text_type(self):
        content_type = self.content_type
        return content_type.startswith('text')

    def get_json(self):
        if not self.content_length:
            # Empty content
            return None
        import json
        return json.loads(self.body, cls=self.json_decoder_cls)

    def get_xml(self):
        from xml.etree.ElementTree import XMLParser
        parser = XMLParser()
        parser.feed(self.body)
        return parser.close()

    def get_file(self):
        raise NotImplementedError
        # from utilmeta.utils.media import File
        # from io import BytesIO
        # return File(
        #     file=BytesIO(self.body),
        #     name=self.gen_file_name(self.content_type)
        # )

    def get_form(self):
        raise NotImplementedError

    def get_text(self):
        return self.body.decode()

    @classmethod
    def gen_file_name(cls, content_type: str) -> str:
        if not content_type:
            content_type = '/'
        maj, sec = content_type.split('/')
        date_str = time_now().strftime('%Y%m%d%H%M%S')
        key = gen_key(6, alnum=True)
        if maj in ('video', 'audio', 'image'):
            name = f'{maj}_{date_str}_{key}.{sec}'
        else:
            name = f'file_{date_str}_{key}'
        return name

    def get_content(self):
        if not self.content_type:
            return self.body
        if self.json_type:
            return self.get_json()
        elif self.form_type:
            return self.get_form()
        elif self.file_type:
            return self.get_file()
        elif self.xml_type:
            return self.get_xml()
        elif self.text_type:
            return self.get_text()
        return None

    @property
    def content(self):
        """
        The loaded body based on the Content-Type
        if content-type is application/json, will be loaded to a dict/list object
        if content-type is form (multipart/form-data), will be loaded to a dict
        with form values and files in it
        """
        if self._override_data:
            pass
        try:
            return self.get_content()
        except NotImplementedError:
            raise
        except Exception as e:
            raise exc.UnprocessableEntity(f'process request body failed with error: {e}')

    @property
    def body(self) -> bytes:
        raise NotImplementedError

    @body.setter
    def body(self, data):
        raise NotImplementedError

    async def async_load(self):
        self.__dict__['body'] = await self.async_read()
        try:
            return self.get_content()
        except NotImplementedError:
            raise
        except Exception as e:
            raise exc.UnprocessableEntity(f'process request body failed with error: {e}')

    async def async_read(self):
        raise NotImplementedError

    def close(self):
        pass

    @property
    def total_traffic(self) -> int:
        req_length = self.content_length
        for key, val in self.headers.items():
            if isinstance(val, str) and isinstance(key, str):
                req_length += len(key) + len(val)
        return req_length
