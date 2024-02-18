import re
from typing import Union, Dict, Type, List, Optional, TYPE_CHECKING
from utilmeta.utils import awaitable, get_doc, regular, duplicate, pop, distinct_add, multi

import inspect
from functools import partial
from .endpoint import Endpoint
from .hook import Hook, ErrorHook, BeforeHook, AfterHook
from ..request import Request, var
from utype.parser.field import Field

if TYPE_CHECKING:
    from .base import API


class APIRoute:
    PATH_REGEX = re.compile("{([a-zA-Z][a-zA-Z0-9_]*)}")
    DEFAULT_PATH_REGEX = '[^/]+'

    def __init__(self,
                 handler: Union[Type['API'], Endpoint],
                 route: Union[str, tuple],
                 name: str,
                 parent: Type['API'] = None,
                 summary: str = None,
                 deprecated: bool = None,
                 private: bool = None,
                 priority: int = None,
                 before_hooks: List[BeforeHook] = (),
                 after_hooks: List[AfterHook] = (),
                 error_hooks: Dict[Type[Exception], ErrorHook] = None, **kwargs):

        from .base import API
        self.method = None
        if isinstance(handler, Endpoint):
            self.method = handler.method
            if handler.is_method and route:
                raise ValueError(f'{self.__class__}: Endpoint method: <{self.method}> '
                                 f'cannot assign route: {repr(route)}, please use another function name')
            if not route:
                route = handler.route
        elif inspect.isclass(handler) and issubclass(handler, API):
            if not route:
                raise ValueError(f'{self.__class__}: API handler: {handler} should specify a route, got empty')
        else:
            raise TypeError(f'{self.__class__}: invalid api class or function: {handler}, must be a '
                            f'Endpoint instance of subclass of API')

        self.name = name
        self.handler = handler
        self.parent = parent
        self.summary = summary
        self.description = get_doc(handler)
        self.deprecated = deprecated
        self.private = private or handler.__name__.startswith('_')
        self.priority = priority
        self.kwargs = kwargs

        if isinstance(route, str):
            route = str(route).strip('/')
        elif isinstance(route, tuple):
            route = self.from_routes(*route)
        else:
            raise TypeError(f'Invalid route: {route}')

        self.route = route
        self.regex_list = []
        self.kwargs_regex = {}

        self.before_hooks = before_hooks or []
        self.after_hooks = after_hooks or []
        self.error_hooks = error_hooks or {}

        self.header_names = []
        self.init_headers()

    def init_headers(self):
        # meant to be inherited
        if isinstance(self.handler, Endpoint):
            self.header_names = self.handler.wrapper.header_names
        else:
            for route in self.handler._routes:
                distinct_add(self.header_names, route.header_names)

            for key, val in self.handler._properties.items():
                name = val.field.name.lower()
                if getattr(val.prop.__in__, '__ident__', None) == 'header':
                    if name not in self.header_names:
                        self.header_names.append(name)
                else:
                    headers = getattr(val.prop, 'headers', None)
                    if headers and multi(headers):
                        distinct_add(self.header_names, [str(v).lower() for v in headers])

    @classmethod
    def from_routes(cls, *routes):
        # meant to be inherited
        return '/'.join([str(v).strip('/') for v in routes])

    def get_field(self, name: str) -> Optional[Field]:
        if isinstance(self.handler, Endpoint):
            f = self.handler.parser.get_field(name)
            if f:
                return f.field
            return None
        field = getattr(self.handler, name, None)
        if isinstance(field, property):
            field = getattr(field.fget, '__field__', None)
        if isinstance(field, Field):
            return field
        elif isinstance(field, type) and issubclass(field, Field):
            return field()
        return None

    @property
    def path_args(self):
        return list(self.kwargs_regex)

    @property
    def options(self):
        if isinstance(self.handler, Endpoint):
            return self.handler.parser.options
        return self.handler.__options__

    def compile_route(self):
        if not self.route:
            self.regex_list = [re.compile('')]
            return

        regs = []
        kwargs_reg = {}
        params: List[str] = self.PATH_REGEX.findall(self.route)

        if not params:
            regs = [re.compile(self.route)]
            if not self.is_endpoint:
                # for API
                regs.append(re.compile(f'{self.route}/(?P<_>.*)'))
            self.regex_list = regs
            return

        d = duplicate(params)
        assert not d, f"Endpoint path: {repr(self.route)} shouldn't contains duplicate param {d}"

        omit = None
        # required path params must before optional ones
        # omit is the mark of the first optional path param
        beg = 0
        divider = []
        suffix = ''

        for i, p in enumerate(params):
            field = self.get_field(p)
            if not field:
                for bf in self.before_hooks:
                    field = bf.parser.get_field(p)
                    if field:
                        break
                if not field:
                    raise ValueError(f'missing path name parameter: {repr(p)}')

            if self.is_endpoint:
                if not field.required:
                    if omit is None:
                        omit = p
                elif omit is not None:
                    raise ValueError(f"Required path argument ({repr(p)}) is after a optional arg "
                                     f"({omit}), which is invalid")

            sub = '{%s}' % p
            end = self.route.find(sub)
            div = self.route[beg:end]
            if beg and not div:
                raise ValueError(f"Endpoint path: {repr(self.route)} param {repr(sub)}"
                                 f" should divide each other with string")
            divider.append((div, p))
            beg = end + len(sub)

        if beg < len(self.route):
            suffix = self.route[beg:]

        pattern = ''
        for div, param in divider:
            path_field = self.get_field(param)
            # use ducked attribute here
            path_regex = getattr(path_field, 'regex', self.DEFAULT_PATH_REGEX)
            div = regular(div)
            pattern += div

            if self.is_endpoint and (omit and param == str(omit) or param != str(omit) and regs):
                # until omit param, do not add pattern
                # after omit param, every param should add a pattern
                regs.append(re.compile(pattern.rstrip('/')))
                # omit does apply for API

            kwargs_reg[param] = path_regex
            pattern += f'(?P<{param}>{path_regex})'

        pattern += suffix
        regs.append(re.compile(pattern))

        if not self.is_endpoint:
            # for API
            regs.append(re.compile(f'{pattern}/(?P<_>.*)'))

        regs.reverse()
        # reverse the reg list so the longest reg match the path first,
        # if success then break, else try out all the regs

        self.regex_list = regs
        self.kwargs_regex = kwargs_reg

    @property
    def is_endpoint(self):
        return isinstance(self.handler, Endpoint)

    @property
    def ident(self):
        if self.method:
            return f'{self.method}:{self.route}'.lower()
        return self.route

    def make_property(self):
        # if with_hooks:
        #     pass
        if self.is_endpoint:
            def getter(api_inst: 'API'):
                return partial(self.handler, api_inst)
        else:
            def getter(api_inst: 'API'):
                return self.handler(api_inst.request)

        return property(getter)

    def match_route(self, request: Request):
        # /doc/{page}
        # /user/* -> UserAPI
        # /http/bin/* -> HttpBinAPI
        route_attr = var.unmatched_route.setup(request)
        path_params_attr = var.path_params.setup(request)
        route = route_attr.get()
        path_params: dict = path_params_attr.get()
        for regex in self.regex_list:
            match = regex.fullmatch(route)
            if match:
                group: dict = match.groupdict()
                if not self.method:
                    # only set path params if route is API
                    # endpoints need to match for multiple methods
                    route_attr.set(pop(group, '_', ''))
                # set path params for endpoint and API in every match
                path_params.update(group)
                path_params_attr.set(path_params)
                return True
        return False

    def match_targets(self, targets: list):
        if isinstance(self.handler, Endpoint):
            return self.handler in targets or self.handler.f in targets
        # otherwise, we only accept the
        # route: someAPI = api(...)(someAPI)
        return self.handler in targets

    def match_hook(self, hook: Hook):
        if hook.hook_all:
            if hook.hook_excludes:
                if self.match_targets(hook.hook_excludes):
                    return False
            return True
        return self.match_targets(hook.hook_targets)

    def hook(self, hook):
        if not self.match_hook(hook):
            # not hook to this route
            return False
        if isinstance(hook, BeforeHook):
            self.before_hooks.append(hook)
        elif isinstance(hook, AfterHook):
            self.after_hooks.append(hook)
        elif isinstance(hook, ErrorHook):
            self.error_hooks.update({err: hook for err in hook.hook_errors})
        return True

    def __enter__(self) -> 'APIRoute':
        """
        Context management can be implied
        like a transaction across the hooks
        :return:
        """
        # enter_route()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
        # exit_route(self, exc_type, exc_val, exc_tb)

    def __call__(self, api: 'API'):
        if api.request.is_options:
            if self.is_endpoint:
                # headers template is dict, while parser.headers can be schema class
                # api.request.allow_headers += tuple(self.handler.parser.headers_template)
                return api.options()
        else:
            # execute before hooks only if request method is not OPTIONS
            for hook in self.before_hooks:
                hook.serve(api)

        result = api.__serve__(self.handler)

        for hook in self.after_hooks:
            result = hook(api, result) or result
            result = hook.process_result(result)

        return result

    @awaitable(__call__)
    async def __call__(self, api: 'API'):
        if api.request.is_options:
            if self.is_endpoint:
                # headers template is dict, while parser.headers can be schema class
                # TODO: allow headers
                # api.request.allow_headers += tuple(self.handler.parser.headers_template)
                return api.options()
        else:
            for hook in self.before_hooks:
                await hook.serve(api)

        result = await api.__serve__(self.handler)

        for hook in self.after_hooks:
            result = await hook(api, result) or result
            result = hook.process_result(result)

        return result

    def generate(self):
        pass

    def clone(self):
        pass
