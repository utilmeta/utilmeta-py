import re
from typing import Union, Dict, Type, List, Optional, TYPE_CHECKING
from utilmeta.utils import awaitable, get_doc, regular, duplicate, pop, distinct_add, multi, PATH_REGEX

import inspect
from functools import partial
from .endpoint import Endpoint
from .hook import Hook, ErrorHook, BeforeHook, AfterHook
from ..request import Request, var
from utype.parser.field import Field

if TYPE_CHECKING:
    from .base import API


class BaseRoute:
    def __init__(self,
                 handler,
                 route: Union[str, tuple],
                 name: str,
                 parent=None,
                 before_hooks: List[BeforeHook] = (),
                 after_hooks: List[AfterHook] = (),
                 error_hooks: Dict[Type[Exception], ErrorHook] = None):

        self.name = name
        self.handler = handler
        self.parent = parent

        if isinstance(route, str):
            route = str(route).strip('/')
        elif isinstance(route, tuple):
            route = self.from_routes(*route)
        else:
            raise TypeError(f'Invalid route: {route}')

        self.route = route
        self.before_hooks = before_hooks or []
        self.after_hooks = after_hooks or []
        self.error_hooks = error_hooks or {}

    @classmethod
    def from_routes(cls, *routes):
        # meant to be inherited
        return '/'.join([str(v).strip('/') for v in routes])

    def match_targets(self, targets: list):
        if self.route in targets:
            # str
            return True
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

    def __enter__(self):
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

    def clone(self):
        return self.__class__(
            self.handler,
            route=self.route,
            name=self.name,
            parent=self.parent,
            before_hooks=list(self.before_hooks),
            after_hooks=list(self.after_hooks),
            error_hooks=dict(self.error_hooks)
        )

    @property
    def no_hooks(self):
        return not self.before_hooks and not self.after_hooks and not self.error_hooks

    def merge_hooks(self, route: 'BaseRoute'):
        # self: near
        # route: far
        if not route or not isinstance(route, BaseRoute):
            return self
        if route.no_hooks:
            return self
        new_route = self.clone()
        new_route.before_hooks = route.before_hooks + self.after_hooks
        new_route.after_hooks = self.after_hooks + route.after_hooks
        error_hooks = dict(route.error_hooks)
        error_hooks.update(self.error_hooks)
        new_route.error_hooks = error_hooks
        return new_route


class APIRoute(BaseRoute):
    PATH_REGEX = PATH_REGEX
    DEFAULT_PATH_REGEX = '[^/]+'

    def __init__(self,
                 handler: Union[Type['API'], Endpoint],
                 route: Union[str, tuple],
                 name: str,
                 parent: Type['API'] = None,
                 summary: str = None,
                 description: str = None,
                 deprecated: bool = None,
                 private: bool = None,
                 priority: int = None,
                 before_hooks: List[BeforeHook] = (),
                 after_hooks: List[AfterHook] = (),
                 error_hooks: Dict[Type[Exception], ErrorHook] = None, **kwargs):

        self.method = None
        from .base import API
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

        super().__init__(
            handler,
            route=route,
            name=name,
            parent=parent,
            before_hooks=before_hooks,
            after_hooks=after_hooks,
            error_hooks=error_hooks
        )

        self.kwargs = kwargs
        self.summary = summary
        self.description = description or get_doc(handler)
        self.deprecated = deprecated
        self.private = private or handler.__name__.startswith('_')
        self.priority = priority
        self.regex_list = []
        self.kwargs_regex = {}
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

    def get_patterns(self):
        pattern = self.route
        for arg in self.path_args:
            pattern = pattern.replace('{%s}' % arg, self.DEFAULT_PATH_REGEX)
        patterns = [pattern]
        if not self.is_endpoint:
            patterns.append(f'{pattern}/.*')
        return patterns

    @classmethod
    def get_pattern(cls, path: str):
        path = path.strip('/')
        params: List[str] = cls.PATH_REGEX.findall(path)

        if not params:
            return re.compile(path)

        pattern = path
        for arg in params:
            pattern = pattern.replace('{%s}' % arg, cls.DEFAULT_PATH_REGEX)

        return re.compile(pattern)

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

    def __call__(self, api: 'API'):
        # ---
        names_var = var.operation_names.setup(api.request)
        names = names_var.get() or []
        names.append(self.name)
        names_var.set(names)
        # ---

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
        # ---
        names_var = var.operation_names.setup(api.request)
        names = await names_var.get() or []
        names.append(self.name)
        names_var.set(names)
        # ---

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
