import inspect
import json
from http.cookies import SimpleCookie
from utilmeta.core.request import Request
from utype.types import *
from utilmeta.utils import Header,\
    get_generator_result, get_doc, is_hop_by_hop, http_time, file_like, \
    STATUS_WITHOUT_BODY, time_now
from utilmeta.utils import exceptions as exc
from utilmeta.utils import Headers
from .backends.base import ResponseAdaptor
from utilmeta.utils.error import Error
from utype.parser.cls import ClassParser
from utype.utils.functional import get_obj_name
import utype
import re
from ..file.base import File


class ResponseClassParser(ClassParser):
    NAMES = ('result', 'headers')

    @classmethod
    def validate_field_name(cls, name: str):
        return name in cls.NAMES


PLAIN = 'text/plain'
JSON = 'application/json'
XML = 'text/xml'
OCTET_STREAM = 'application/octet-stream'


class Response:
    __parser_cls__ = ResponseClassParser
    __parser__: ResponseClassParser
    __json_encoder_cls__ = utype.JSONEncoder

    # -- params --
    result_key: str = None
    message_key: str = None
    count_key: str = None
    state_key: str = None

    message_header: str = None
    count_header: str = None
    state_header: str = None
    # ----

    result = None
    state = None
    # when response is json type and __params__ specified result is the inner result key
    # otherwise result is an alias of data, but often be inherited and annotated
    strict: bool = None

    status: int = None
    reason: str = None
    charset: str = None
    content_type: str = None
    headers: Headers        # can be any inherited map, or assign to a HeadersSchema
    cookies: SimpleCookie
    name: str = None
    description: str = None

    wrapped: bool = False

    def __class_getitem__(cls, item):
        """
        we DO NOT use a generic type here because we don't want user to inherit both Response and Generate[ResultType]
        instead, when user are declaring the response for API (which means they will probably
        no need to ref to the result, and thus no need to hint type), they can use this method to
        quickly generate a new Response class with such result type

        class response(Response):
            result_data_key: str = 'data'

        def operationA(self) -> response[OperationAResult]: pass
        def operationB(self) -> response[OperationBResult]: pass

        but in SDK, where you need to reference to the result and need to hint type, we recommend to use

        class OperationAResponse(Response):
            result_key: str = 'data'
            result: OperationAResult

        which is much clearer, support natively by type checkers,
        and since the SDK code is basically auto-generated,
        it's considered the best practice for SDK
        """
        class _response(cls):
            result: item

        _response.__name__ = _response.__qualname__ = get_obj_name(item) + 'Response'

        return _response

    def __init_subclass__(cls, **kwargs):
        cls.__parser__ = cls.__parser_cls__.apply_for(cls)
        cls.description = cls.description or get_doc(cls)
        cls.wrapped = bool(cls.result_key or cls.count_key or cls.message_key or cls.state_key)

        if not cls.content_type and cls.wrapped:
            cls.content_type = JSON

        keys = [cls.result_key, cls.message_key, cls.count_key, cls.state_key]
        wrap_keys = [k for k in keys if k is not None]
        if len(set(wrap_keys)) < len(wrap_keys):
            raise ValueError(f'{cls.__name__}: conflict response keys: {wrap_keys}')

    def __init__(self,
                 result=None,
                 *,
                 state=None,
                 message=None,      # can be str or error or dict/list of messages
                 count: int = None,
                 reason: str = None,
                 status: int = None,
                 extra: dict = None,

                 content: Union[bytes, dict, list, str] = None,
                 content_type: str = None,
                 charset: str = None,
                 headers=None,
                 cookies=None,

                 # store the original context
                 request: Request = None,
                 response=None,
                 error: Union[Error, Exception] = None,
                 file=None,
                 # metadata
                 mocked: bool = False,
                 cached: bool = False,
                 timeout: bool = False,
                 aborted: bool = False,
                 # when timeout set to True, raw_response is None
                 stack: list = None
                 ):

        self.adaptor = ResponseAdaptor.dispatch(response) if response else None
        self._request = request
        self._content = content
        self._extra = extra

        if self.adaptor:
            status = status or self.adaptor.status
            reason = reason or self.adaptor.reason
            charset = charset or self.adaptor.charset
            content_type = content_type or self.adaptor.content_type
            headers = headers or self.adaptor.headers
            cookies = cookies or self.adaptor.cookies

        self.reason = reason or self.reason
        self.status = status or self.status
        self.charset = charset or self.charset
        self.content_type = content_type or self.content_type
        self.state = state or self.state
        self.message = message
        self.count = count

        self.init_headers(headers)
        self.cookies = SimpleCookie(cookies or {})

        self._cached = cached
        self._mocked = mocked
        # this is just a lazy shortcut that does not deal with TimeoutError
        self._timeout = timeout
        self._aborted = aborted

        # stack of the response redirect/retry/cache chain
        # 1. response: 302 (redirect1)
        # 2. response: 301 (redirect2)
        # 3. response: retry 1
        # 4. response: retry 2
        self._stack = stack

        self._file = None
        self._error = None
        self._setup_time = time_now()

        self.init_error(error)
        self.init_result(result)
        self.init_file(file)

        self.parse_headers()
        self.status = self.status or 200
        # default status is 200
        if self.state is None:
            self.state = 1 if self.success else 0
        # set default state after status

        # build content at last
        self.build_content()

        # represent the loaded data
        self._data = None

    def __contains__(self, item):
        return item in self.headers

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        return self.adaptor.close()

    def parse_content(self):
        if self.result is not None:
            return
        if isinstance(self._content, dict) and self.wrapped:
            if self.result_key:
                self.result = self._content.get(self.result_key, self._content)
            if self.message_key:
                self.message = self._content.get(self.message_key)
            if self.state_key:
                self.state = self._content.get(self.state_key)
            if self.count_key:
                self.count = self._content.get(self.count_key)
        else:
            self.result = self._content

    def match(self):
        if not self.adaptor:
            return True
        if self.__class__.status and self.__class__.status != self.status:
            return False
        if self.__class__.state and self.__class__.state != self.state:
            return False
        if self.__class__.content_type and self.__class__.content_type != self.content_type:
            return False
        return True

    @classmethod
    def is_cls(cls, r):
        return inspect.isclass(r) and issubclass(r, cls)

    @classmethod
    def _response_like(cls, resp):
        status = getattr(resp, 'status', getattr(resp, 'status_code', None))
        if status and isinstance(status, int):
            return True
        return False

    def init_headers(self, headers):
        if self.strict:
            field = self.__parser__.fields.get('headers')
            if field:
                headers = field.parse_value(headers, context=self.__parser__.options.make_context())
        self.headers = Headers(headers or {})

    def init_result(self, result):
        if hasattr(result, '__next__'):
            # convert generator yield result into list
            # result = list(result)
            result = get_generator_result(result)

        if isinstance(result, (Exception, Error)):
            self.init_error(result)
            result = self.result

        if self.strict:
            field = self.__parser__.fields.get('result')
            if field:
                result = field.parse_value(result, context=self.__parser__.options.make_context())

        if not self.adaptor and self._response_like(result):
            self.adaptor = ResponseAdaptor.dispatch(result)
            self.result = None
            return

        if file_like(result):
            self.init_file(result)
            return

        self.result = result

    def init_file(self, file):
        if not file:
            return
        if isinstance(file, File):
            self._file = file.file
            return
        if not file_like(file):
            return
        self._file = file

    def init_error(self, error):
        if isinstance(error, Exception):
            error = Error(error)
        elif not isinstance(error, Error):
            return
        if not self.status:
            self.status = error.status
        if self.state is None:
            self.state = error.state
        if self.result is None:
            self.result = error.result
        if self.headers is None:
            self.headers = error.headers
        if not self.message:        # empty string ''
            self.message = str(error.exception)
        error.log(console=True)
        self._error = error

    def build_data(self):
        if self.wrapped:
            # wrap it inside a dict
            data = dict(self._extra or {})
            if self.result_key:
                data[self.result_key] = self.result
            if self.message_key:
                data[self.message_key] = self.message or ''
            if self.state_key:
                data[self.state_key] = self.state
            if self.count_key:
                data[self.count_key] = self.count or 0
            return data
        else:
            data = self.result
        return data

    def build_content(self):
        if self._content is not None:
            return
        if self.adaptor:
            self._content = self.adaptor.get_content()
            self.parse_content()
            return
        if self.status in STATUS_WITHOUT_BODY:
            return
        if self._file:
            self._content = self._file
            return
        data = self.build_data()
        if hasattr(data, '__iter__') and not isinstance(data, (bytes, memoryview, str, list, dict)):
            # must convert to list iterable
            # this data is guarantee that not file_like
            data = list(data)
        if data is None or data == '':
            data = b''
        self._content = data
        self.build_content_type()

    def build_content_type(self):
        if self.content_type is not None:
            return
        if hasattr(self._content, 'content_type'):
            # like File
            self.content_type = self._content.content_type
            return
        if not self._content:
            # no content. no type
            return
        if isinstance(self._content, (dict, list)):
            self.content_type = JSON
        elif isinstance(self._content, str):
            self.content_type = PLAIN
        elif isinstance(self._content, bytes) or file_like(self._content):
            self.content_type = OCTET_STREAM

    @property
    def data(self):
        if self._data:
            return self._data
        data = self.body
        if not data:
            return None
        if self.content_type:
            if self.content_type.startswith(JSON):
                data = json.loads(data)
            elif self.content_type.startswith('text/'):
                data = data.decode(errors='ignore')
        self._data = data
        return data

    # @classmethod
    # def get_data(cls, resp: 'Response'):
    #     body = resp.body
    #     if not body:
    #         return None
    #     if resp.content_type:
    #         if resp.content_type.startswith(JSON):
    #             return json.loads(body)
    #         elif resp.content_type.startswith('text/'):
    #             return body.decode(errors='ignore')
    #     return body

    def __str__(self):
        reason = f' {self.reason}' if self.reason else ''
        return f'{self.__class__.__name__} [{self.status}{reason}] ' \
               f'"{self.request.method.upper()} /%s"' % self.request.encoded_path.strip('/') if self.request else ''

    def __repr__(self):
        return self.__str__()

    def print(self):
        print(str(self))
        content_type = self.content_type or self.headers.get('content-type')
        content_length = self.content_length
        if content_type:
            print(f'{content_type} ({content_length or 0})')
            data = self.data
            if data:
                print(data)
        print('')

    def dump_json(self, encoder=None, ensure_ascii: bool = False, **kwargs):
        import json
        kwargs.update(ensure_ascii=ensure_ascii)
        return json.dumps(self._content, cls=encoder or self.__json_encoder_cls__, **kwargs)

    def parse_headers(self):
        if self.message_header:
            self.message = self.headers.get(self.message_header) or self.message
        if self.state_header:
            self.state = self.headers.get(self.state_header) or self.state
        if self.count_header:
            self.count = self.headers.get(self.count_header) or self.count

    def build_headers(self):
        if self.adaptor:
            self.parse_headers()
            return
        if self.message_header and self.message:
            self.headers[self.message_header] = self.message
        if self.state_header and self.state is not None:
            self.headers[self.state_header] = self.state
        if self.count_header and self.count is not None:
            self.headers[self.count_header] = self.count

    @property
    def request(self):
        return self._request

    @request.setter
    def request(self, r):
        if self._request:
            return
        self._request = r

    @property
    def content(self):
        if self._content is not None:
            return self._content
        if self.adaptor:
            return self.adaptor.get_content()
        return None

    @property
    def raw_response(self):
        # HTTPResponse: internal=False, outside API
        # HttpResponse: internal=True, current API (often used in test mode)
        # NOTE: cached response will not have this property to maintain space efficiency
        return self.adaptor.response if self.adaptor else None

    @raw_response.setter
    def raw_response(self, resp):
        self.adaptor = ResponseAdaptor.dispatch(resp)

    @property
    def original_response(self) -> Optional['Response']:
        # from 3xx redirect response, original_response is that 3xx response
        # including cached 304 responses
        if self._stack:
            return self._stack[0]
        return None

    def push_response_stack(self, resp: 'Response'):
        if not isinstance(resp, Response):
            raise TypeError(f'Invalid response: {resp}')
        self._stack.append(resp)

    @property
    def url(self):
        if not self.request:
            return None
        return self.request.url

    @property
    def time(self):
        if not self.request:
            return None
        return self.request.time

    @property
    def duration(self) -> timedelta:
        return timedelta(milliseconds=self.duration_ms)

    @property
    def duration_ms(self) -> int:
        if not self.request:
            return 0
        st = self.request.time
        et = self._setup_time
        if st and et:
            return max(0, int((et - st).total_seconds() * 1000))
        return 0

    @property
    def language(self):
        return self.headers.get(Header.CONTENT_LANGUAGE)

    @property
    def content_length(self):
        return self.headers.get(Header.LENGTH)

    @property
    def count(self):
        return self._count

    @count.setter
    def count(self, val: int):
        self._count = int(val or 0)

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, val):
        self._message = val

    @property
    def file(self):
        if self.adaptor:
            return self.adaptor.get_file()
        return self._file

    @file.setter
    def file(self, file):
        self.init_file(file)

    @property
    def json(self) -> Union[dict, list, None]:
        if self.adaptor:
            return self.adaptor.get_json()
        if isinstance(self._content, (dict, list)):
            return self._content
        return None

    @property
    def text(self) -> str:
        if self.adaptor:
            return self.adaptor.get_text()
        if isinstance(self._content, str):
            return self._content
        return ''

    def set_header(self, name: str, value):
        self.headers[name] = value

    def update_headers(self, **headers):
        self.headers.update(**headers)

    def set_cookie(
        self,
        key: str,
        value: str = "",
        max_age: int = None,
        expires: Union[str, int, datetime] = None,
        path: str = "/",
        domain: str = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: str = None
    ):
        self.cookies[key] = value
        if expires is not None:
            if isinstance(expires, datetime):
                max_age = max(0, int((datetime.now() - expires).total_seconds()))
                expires = http_time(expires)
            elif isinstance(expires, (int, float)):
                expires = http_time(datetime.utcfromtimestamp(expires), to_utc=False)
            self.cookies[key]['expires'] = expires
        else:
            self.cookies[key]['expires'] = ''

        if max_age is not None:
            self.cookies[key]['max-age'] = int(max_age)
            if not expires:
                # IE requires expires, so set it if hasn't been already.
                self.cookies[key]['expires'] = http_time(datetime.now() + timedelta(seconds=max_age))

        if path is not None:
            self.cookies[key]['path'] = path
        if domain is not None:
            self.cookies[key]['domain'] = domain
        if secure:
            self.cookies[key]['secure'] = True
        if httponly:
            self.cookies[key]['httponly'] = True
        if samesite:
            if samesite.lower() not in ('lax', 'none', 'strict'):
                raise ValueError('samesite must be "lax", "none", or "strict".')
            self.cookies[key]['samesite'] = samesite.lower()

    def delete_cookie(self, key: str, path: str = "/", domain: str = None) -> None:
        self.set_cookie(key, expires=0, max_age=0, path=path, domain=domain)

    def prepare_headers(self, with_content_type: bool = False) -> List[Tuple[str, str]]:
        header_values = []
        for key, val in self.headers.items():
            if self.adaptor and is_hop_by_hop(key):
                continue
            if str(key).lower() == 'content-type':
                with_content_type = False
            header_values.append((str(key), str(val)))
        if with_content_type and self.content_type:
            content_type = self.content_type
            if content_type and self.charset:
                content_type = f'{content_type}; charset={self.charset}'
            header_values.append(('Content-Type', content_type))
        for cookie in self.cookies.values():
            header_values.append(('Set-Cookie', cookie.OutputString()))
        return header_values

    def prepare_body(self):
        if self.adaptor:
            return self.adaptor.body
        if self._file:
            return self._file
        if self.content_type and self.content_type.startswith(JSON):
            return self.dump_json()
        # this content might not be bytes, leave the encoding to the adaptor
        return self._content

    async def load(self):
        await self.adaptor.async_load()

    @property
    def body(self) -> bytes:
        if self.adaptor:
            return self.adaptor.body
        body = self.prepare_body()
        if hasattr(body, 'read'):
            return body.read()      # noqa
        if isinstance(body, bytes):
            return body
        if not isinstance(body, str):
            body = str(body)
        return body.encode(self.charset or 'utf-8', errors='replace')

    @property
    def error(self) -> Optional[Error]:
        if self.success:
            return None
        if self._error:
            return self._error
        e = exc.HttpError.STATUS_EXCEPTIONS.get(self.status, exc.ServerError)(self.message)
        return Error(e)

    @error.setter
    def error(self, e):
        self.init_error(e)

    def throw(self):
        err = self.error
        if err:
            raise err.throw()

    # def valid(self, *_, **__):
    #     return self.success

    @classmethod
    def mock(cls):
        pass

    @property
    def success(self):
        if not self.status:
            return False
        if self.status >= 400:
            return False
        return True

    @classmethod
    def server_error(cls, message=''):
        return cls(message=message, status=500)

    @classmethod
    def permission_denied(cls, message=''):
        return cls(message=message, status=500)

    @classmethod
    def request_timeout(cls):
        return cls(status=408)

    @classmethod
    def gone(cls):
        return cls(status=410)

    @classmethod
    def created(cls):
        return cls(status=201)

    @classmethod
    def accepted(cls):
        return cls(status=202)

    @classmethod
    def bad_request(cls, message=''):
        return cls(message=message, status=400)

    @classmethod
    def not_found(cls, message=''):
        return cls(message=message, status=404)

    @classmethod
    def not_modified(cls):
        return cls(status=304)

    def html(self, content):
        pass

    def patch_vary_headers(self, *newheaders):
        """
        Add (or update) the "Vary" header in the given HttpResponse object.
        newheaders is a list of header names that should be in "Vary". If headers
        contains an asterisk, then "Vary" header will consist of a single asterisk
        '*'. Otherwise, existing headers in "Vary" aren't removed.
        """
        # Note that we need to keep the original order intact, because cache
        # implementations may rely on the order of the Vary contents in, say,
        # computing an MD5 hash.

        if "Vary" in self.headers:
            vary_headers = re.compile(r"\s*,\s*").split(self.headers["Vary"])
        else:
            vary_headers = []
        # Use .lower() here so we treat headers as case-insensitive.
        existing_headers = {header.lower() for header in vary_headers}
        additional_headers = [
            newheader
            for newheader in newheaders
            if newheader.lower() not in existing_headers
        ]
        vary_headers += additional_headers
        if "*" in vary_headers:
            self.headers["Vary"] = "*"
        else:
            self.headers["Vary"] = ", ".join(vary_headers)


@utype.register_transformer(Response)
def transform_response(transformer, resp, cls):
    if isinstance(resp, ResponseAdaptor):
        resp = cls(response=resp)
    elif not isinstance(resp, Response):
        resp = cls(resp)
    return resp
