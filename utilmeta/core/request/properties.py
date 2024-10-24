import inspect
from utilmeta.utils import exceptions as exc
from utilmeta.utils import awaitable
from .base import Request
from utilmeta.utils.context import Property
from typing import Union, Optional, List, Mapping, Any
from datetime import datetime
from utype.parser.field import ParserField, Field
from utype.utils.datastructures import unprovided
from . import var
from ipaddress import IPv6Address, IPv4Network, IPv6Network, IPv4Address


__all__ = [
    'URL',
    'Host',
    'PathParam',
    'FilePathParam',
    'SlugPathParam',
    'BodyParam',
    'Body',
    'Form',
    'Json',
    'EncodingField',
    'Query',
    'QueryParam',
    'Headers',
    'HeaderParam',
    'Cookies',
    'CookieParam',
    'UserAgent',
    'Address',
    'Time'
]


class Path(Property):
    __ident__ = 'path'

    @classmethod
    def getter(cls, request: Request, *keys: str):
        return request.path


class URL(Property):
    __ident__ = 'url'

    @classmethod
    def getter(cls, request: Request, field: ParserField = None):
        return request.url


class Host(Property):
    @classmethod
    def getter(cls, request: Request, field: ParserField = None):
        return request.host

    def __init__(self,
                 allow_list: list = None,
                 block_list: list = None,
                 local_only: bool = False,
                 private_only: bool = False,
                 public_only: bool = False,
                 ):
        super().__init__()
        self.allow_list = allow_list
        self.block_list = block_list
        self.local_only = local_only
        self.private_only = private_only
        self.public_only = public_only


class Body(Property):
    PLAIN = 'text/plain'
    JSON = 'application/json'
    FORM_URLENCODED = 'application/x-www-form-urlencoded'
    FORM_DATA = 'multipart/form-data'
    XML = 'application/xml'
    OCTET_STREAM = 'application/octet-stream'

    __ident__ = 'body'
    __name_prefix__ = 'request'
    __no_default__ = True

    content_type = None

    def getter(self, request: Request, field: ParserField = None):
        self.validate_content_type(request)
        data = request.data
        var_data = var.data.setup(request)
        if not var_data.contains():
            var_data.set(data)
        self.validate_max_length(request)
        return data

    @awaitable(getter)
    async def getter(self, request: Request, field: ParserField = None):
        self.validate_content_type(request)
        var_data = var.data.setup(request)
        if var_data.contains():
            return await var_data.get()
        data = await request.adaptor.async_load()
        var_data.set(data)
        self.validate_max_length(request)
        return data

    def validate_content_type(self, request: Request):
        if self.content_type and request.content_type != self.content_type:
            raise exc.UnprocessableEntity('invalid content type')

    def validate_max_length(self, request: Request):
        if self.max_length and request.content_length and request.content_length > self.max_length:
            raise exc.RequestEntityTooLarge

    def __init__(self, content_type: str = None, *,
                 description: str = None,
                 example: Any = None,
                 # options=None,
                 # default=unprovided,
                 max_length: int = None, **kwargs):
        super().__init__(
            max_length=max_length,
            # options=options,
            description=description,
            example=example,
            **kwargs
        )
        # if content_type:
        self.content_type = content_type
        # self.options = options
        self.max_length = max_length  # Body Too Long


class Json(Body):
    content_type = 'application/json'

    def __init__(self, *,
                 description: str = None,
                 example: Any = None, **kwargs):
        super().__init__(
            self.content_type,
            description=description,
            example=example,
            **kwargs
        )

    def getter(self, request: Request, field: ParserField = None):
        if not request.adaptor.json_type:
            raise exc.UnprocessableEntity(f'invalid content type')
        return request.adaptor.get_json()

    @awaitable(getter)
    async def getter(self, request: Request, field: ParserField = None):
        if not request.adaptor.json_type:
            raise exc.UnprocessableEntity(f'invalid content type')
        return await request.adaptor.async_load()


class Form(Body):
    content_type = 'multipart/form-data'

    def __init__(self, *,
                 description: str = None,
                 example: Any = None, **kwargs):
        super().__init__(
            self.content_type,
            description=description,
            example=example,
            **kwargs
        )

    def validate_content_type(self, request: Request):
        if self.content_type and request.content_type not in (Body.FORM_URLENCODED, Body.FORM_DATA):
            raise exc.UnprocessableEntity('invalid content type')

    def getter(self, request: Request, field: ParserField = None):
        if not request.adaptor.form_type:
            raise exc.UnprocessableEntity(f'invalid content type')
        return request.adaptor.get_form()

    @awaitable(getter)
    async def getter(self, request: Request, field: ParserField = None):
        if not request.adaptor.form_type:
            raise exc.UnprocessableEntity(f'invalid content type')
        return await request.adaptor.async_load()


class ObjectProperty(Property):
    def init(self, field: ParserField):
        t = field.type
        if not t or not isinstance(t, type) or isinstance(None, t):
            raise TypeError(f'{self.__class__}: {repr(field.name)} should specify a valid object type')
        if not issubclass(t, Mapping):
            from utype.parser.cls import ClassParser
            parser = getattr(t, '__parser__', None)
            if not isinstance(parser, ClassParser):
                raise TypeError(f'{self.__class__}: {repr(field.name)} should specify a valid object type, got {t}')
        return super().init(field)


class Query(ObjectProperty):
    __ident__ = 'query'
    __name_prefix__ = 'request'
    __type__ = dict
    __no_default__ = True

    @classmethod
    def getter(cls, request: Request, field: ParserField = None):
        return request.query

    # def init(self, field: ParserField):
    #     pass

    # do not check explicitly for now
    # because user can for example use "str" as type to get the query dict in string
    # we generating document, we will try to extract json-schema specs from the input type
    # if failed to do so, we will just leave it empty
    # @classmethod
    # def validate(cls, field: ParserField):
    #     if isinstance(field.type, type):
    #         if not isinstance(field.type, Mapping):
    #             pass

    # @classmethod
    # def valid(cls, data: dict):
    #     if isinstance(data, ForwardRef):
    #         return
    #     import inspect
    #     if isinstance(data, Rule):
    #         if data.type and issubclass(data.type, dict):
    #             return
    #         data = data.template
    #     if inspect.isclass(data):
    #         assert issubclass(data, dict), f"Request Query type should be dict subclass, got {data}"
    #     elif isinstance(data, dict):
    #         for k in data.keys():
    #             assert isinstance(k, str)
    #             if k.endswith('[]'):
    #                 raise ValueError(f'Request Query template key cannot endswith "[]", '
    #                                  f'it is reserved for list QueryString params parse')
    #         f = Media.find_file(data)
    #         if f:
    #             raise TypeError(f"Invalid File param: {f} in Request.Query")
    #     else:
    #         raise TypeError(f"Request Query template should be a dict, got {data}")


class Headers(ObjectProperty):
    __ident__ = 'header'  # according to OpenAPI, not "headers"
    __name_prefix__ = 'request'
    __type__ = dict
    __no_default__ = True

    @classmethod
    def getter(cls, request: Request, field: ParserField = None):
        return request.headers

    # @classmethod
    # def valid(cls, data: dict):
    #     if isinstance(data, ForwardRef):
    #         return
    #     import inspect
    #     if isinstance(data, Rule):
    #         if data.type and issubclass(data.type, dict):
    #             return
    #         data = data.template
    #     if inspect.isclass(data):
    #         assert issubclass(data, dict), f"Request Headers type should be dict subclass, got {data}"
    #     elif isinstance(data, dict):
    #         f = Media.find_file(data)
    #         if f:
    #             raise TypeError(f"Invalid File param: {f} in Request.Headers")
    #     else:
    #         raise TypeError(f"Request Headers template should be a dict, got {data}")


class Cookies(ObjectProperty):
    __ident__ = 'cookie'  # according to OpenAPI, not "cookies"
    __name_prefix__ = 'request'

    @classmethod
    def getter(cls, request: Request, field: ParserField = None):
        return request.cookies


class RequestParam(Property):
    __name_prefix__ = 'request'

    def get_value(self, data: Mapping, field: ParserField):
        if isinstance(data, Mapping):
            if self.case_insensitive:
                data = {k.lower(): v for k, v in data.items()}
            for key in field.all_aliases:
                if key in data:
                    return data[key]
        return unprovided

    def getter(self, request: Request, field: ParserField = None):
        if not field:
            raise ValueError(f'field required')
        data = self.get_mapping(request)
        return self.get_value(data, field)

    @awaitable(getter)
    async def getter(self, request: Request, field: ParserField = None):
        if not field:
            raise ValueError(f'field required')
        data = self.get_mapping(request)
        if inspect.isawaitable(data):
            data = await data
        return self.get_value(data, field)

    @classmethod
    def get_mapping(cls, request: Request) -> Optional[Mapping]:
        raise NotImplementedError

    @classmethod
    @awaitable(get_mapping)
    async def get_mapping(cls, request: Request) -> Optional[Mapping]:
        raise NotImplementedError

    def __init__(self,
                 alias: str = None,
                 default=unprovided,
                 required: bool = None,
                 style: str = None,
                 **kwargs):
        if required:
            default = unprovided
        super().__init__(
            alias=alias or self.alias_generator,
            default=default,
            required=required,
            **kwargs
        )
        self.style = style
        # refer to https://swagger.io/specification/

    alias_generator = None

    # def set_key(self, key: str):
    #     if self._keys:
    #         raise ValueError(f'{self} keys is already set, you cannot use one param to assign multiple args')
    #     keys = set()
    #     if self.alias:
    #         keys.add(self.alias)
    #     aliases = self.alias_generator(key)
    #     if aliases:
    #         if multi(aliases):
    #             keys.update(aliases)
    #         else:
    #             keys.add(aliases)
    #     if self.rule.aliases:
    #         keys.update(self.rule.aliases)
    #     self._keys = keys

    # @property
    # def keys(self) -> Set[str]:
    #     return self._keys


# single param


class PathParam(RequestParam):
    @classmethod
    def get_mapping(cls, request: Request) -> Optional[Mapping]:
        return var.path_params.getter(request)

    __in__ = Path
    __no_default__ = True

    regex = '[^/]+'  # default regex, can be override

    def __init__(self, regex: str = None, *, min_length: str = None, max_length: str = None,
                 required: bool = True, default=unprovided, **kwargs):
        if not regex:
            if min_length:
                if max_length:
                    regex = '(.{%s,%s})' % (min_length, max_length)
                elif min_length == 1:
                    regex = '(.+)'
                else:
                    regex = '(.{%s,})' % min_length
            elif max_length:
                regex = '(.{0,%s})' % max_length
        if regex:
            self.regex = regex
        self.min_length = min_length
        self.max_length = max_length

        if not unprovided(default):
            required = False

        self.required = required

        super().__init__(
            regex=self.regex,
            required=required,
            default=default,
            **kwargs
        )


class SlugPathParam(PathParam):
    regex = r"[a-z0-9]+(?:-[a-z0-9]+)*"


class FilePathParam(PathParam):
    regex = r'(.*)'


class QueryParam(RequestParam):
    __in__ = Query

    @classmethod
    def get_mapping(cls, request: Request):
        return request.query


class BodyParam(RequestParam):
    __in__ = Body

    @classmethod
    def get_mapping(cls, request: Request):
        data = var.data.setup(request)
        if data.contains():
            return data.get()
        if request.adaptor.json_type:
            mp = request.adaptor.get_json()
        elif request.adaptor.form_type:
            mp = request.adaptor.get_form()
        else:
            raise exc.UnprocessableEntity(f'invalid content type, must be json or form')
        data.set(mp)
        return mp

    @classmethod
    @awaitable(get_mapping)
    async def get_mapping(cls, request: Request):
        data = var.data.setup(request)
        if data.contains():
            return await data.get()
        if request.adaptor.json_type or request.adaptor.form_type:
            mp = await request.adaptor.async_load()
        else:
            raise exc.UnprocessableEntity(f'invalid content type, must be json or form')
        data.set(mp)
        return mp


class EncodingField(Field):
    def __init__(self,
                 content_type: str = None,
                 # support for mixed encoding body (multipart/mixed)
                 # will integrate into encoding in requestBody
                 *,
                 description: str = None,
                 example: Any = None,
                 # options=None,
                 max_length: int = None,
                 headers: dict = None,
                 **kwargs):
        super().__init__(
            max_length=max_length,
            # options=options,
            description=description,
            example=example,
            **kwargs
        )
        self.content_type = content_type
        # self.options = options
        self.max_length = max_length  # Body Too Long
        self.headers = headers


class HeaderParam(RequestParam):
    __in__ = Headers

    @classmethod
    def get_mapping(cls, request: Request):
        return request.headers

    @classmethod
    def alias_generator(cls, key: str):
        return key.replace('_', '-')

#
# class Authorization(HeaderParam):
#     def __init__(self,
#                  scheme: str = 'bearer',
#                  default=unprovided,
#                  required: bool = None,
#                  style: str = None,
#                  **kwargs):
#         super().__init__(
#             alias='authorization',
#             default=default,
#             required=required,
#             style=style,
#             **kwargs
#         )
#         self.scheme = scheme
#
#     def get_value(self, data: Mapping, field: ParserField):
#         value = super().get_value(data, field)
#         if isinstance(value, str):
#             if ' ' in value:
#                 return value.split(' ')[1]
#         return value


class CookieParam(RequestParam):
    __in__ = Cookies

    @classmethod
    def get_mapping(cls, request: Request):
        return request.cookies


# class SessionParam(RequestParam):
#     __in__ = Session
#     __private__ = True
#     # This param is not sensible for client
#
#     @classmethod
#     def get_mapping(cls, request: Request):
#         return request.session


class UserAgent(Property):
    __in__ = Headers
    __key__ = 'user-agent'

    @classmethod
    def getter(cls, request: Request, field: ParserField = None):
        return request.headers.get('User-Agent', unprovided)

    def __init__(self,
                 regex: str = None,
                 os_regex: str = None,
                 device_regex: str = None,
                 browser_regex: str = None,
                 bot: bool = None,
                 pc: bool = None,
                 mobile: bool = None,
                 tablet: bool = None):
        super().__init__(regex=regex)
        # None: no restriction whether or not agent is match
        # True: request agent must be ...
        # False: request agent must not be ...
        if bot is False:
            assert not pc and not mobile and not tablet
        assert [pc, mobile, tablet].count(True) <= 1, f'Request Agent cannot specify multiple platform'
        assert {bot, pc, mobile, tablet} != {None}, f'Request Agent must specify some rules'
        import re
        self.regex = re.compile(regex) if regex else None
        self.os_regex = re.compile(os_regex) if os_regex else None
        self.device_regex = re.compile(device_regex) if device_regex else None
        self.browser_regex = re.compile(browser_regex) if browser_regex else None
        self.bot = bot
        self.pc = pc
        self.mobile = mobile
        self.tablet = tablet

    def runtime_validate(self, user_agent):
        try:
            from user_agents.parsers import UserAgent   # noqa
        except ModuleNotFoundError:
            raise ModuleNotFoundError('UserAgent validation requires to install [user_agents] package')

        user_agent: UserAgent

        if self.regex:
            if not self.regex.search(user_agent.ua_string):
                raise exc.PermissionDenied('Request Agent is denied')

        if self.os_regex:
            if not self.os_regex.search(user_agent.os):
                raise exc.PermissionDenied('Request Agent is denied')

        if self.device_regex:
            if not self.device_regex.search(user_agent.device):
                raise exc.PermissionDenied('Request Agent is denied')

        if self.browser_regex:
            if not self.browser_regex.search(user_agent.browser):
                raise exc.PermissionDenied('Request Agent is denied')

        if self.bot is not None:
            if self.bot ^ user_agent.is_bot:
                raise exc.PermissionDenied('Request Agent is denied')

        if self.pc is not None:
            if self.pc ^ user_agent.is_pc:
                raise exc.PermissionDenied('Request Agent is denied')

        if self.mobile is not None:
            if self.mobile ^ user_agent.is_mobile:
                raise exc.PermissionDenied('Request Agent is denied')

        if self.tablet is not None:
            if self.tablet ^ user_agent.is_tablet:
                raise exc.PermissionDenied('Request Agent is denied')


class Address(Property):
    __type__ = Union[IPv4Address, IPv6Address]

    @classmethod
    def getter(cls, request: Request, field: ParserField = None):
        return request.ip_address

    def __init__(self,
                 block_list: List[Union[IPv4Network, IPv6Network, str]] = None,
                 allow_list: List[Union[IPv4Network, IPv6Network, str]] = None,
                 ipv4_only: bool = None,
                 ipv6_only: bool = None,
                 local_only: bool = None,  # for micro-service integration
                 private_only: bool = None,
                 public_only: bool = None):
        super().__init__()
        self.block_list = block_list
        self.allow_list = allow_list
        self.local_only = local_only
        self.private_only = private_only
        self.public_only = public_only
        self.ipv4_only = ipv4_only
        self.ipv6_only = ipv6_only


class Time(Property):
    __type__ = datetime

    @classmethod
    def getter(cls, request: Request, field: ParserField = None):
        return request.time

    def __init__(self,
                 not_before: datetime = None,  # open time
                 not_after: datetime = None,  # close time
                 time_zone: str = None,
                 ):
        super().__init__(required=False)
        self.not_before = not_before
        self.not_after = not_after
        self.time_zone = time_zone
