# import inspect
# import re
import warnings

import django
import sys
from functools import update_wrapper
from django.http.response import HttpResponseBase
from django.core.management import execute_from_command_line
from django.core.handlers.base import BaseHandler
from django.utils.deprecation import MiddlewareMixin
from django.urls import re_path, URLPattern, path, include

from utilmeta import UtilMeta
from utilmeta.core.orm.backends.django.database import DjangoDatabaseAdaptor
from utilmeta.core.request.backends.django import DjangoRequestAdaptor
from utilmeta.core.response.backends.django import DjangoResponseAdaptor
from utilmeta.core.request import Request
from utilmeta.core.api import API
from utilmeta.utils import Header, localhost, pop
from utilmeta.core.response import Response
from utilmeta.core.server.backends.base import ServerAdaptor
from .settings import DjangoSettings
import contextvars

_current_request = contextvars.ContextVar('_django.request')
_current_response = contextvars.ContextVar('_django.response')


class DebugCookieMiddleware(MiddlewareMixin):
    def process_response(self, request, response: HttpResponseBase):
        origin = request.headers.get(Header.ORIGIN)
        if origin and localhost(origin):
            for key in response.cookies.keys():
                cookie = response.cookies[key]
                pop(cookie, 'domain')
                if not localhost(request.get_host()):
                    cookie['samesite'] = 'None'
        return response


class DjangoServerAdaptor(ServerAdaptor):
    backend = django
    request_adaptor_cls = DjangoRequestAdaptor
    response_adaptor_cls = DjangoResponseAdaptor
    sync_db_adaptor_cls = DjangoDatabaseAdaptor
    default_asynchronous = False
    URLPATTERNS = 'urlpatterns'
    DEFAULT_PORT = 8000
    DEFAULT_HOST = '127.0.0.1'
    settings_cls = DjangoSettings

    def __init__(self, config: UtilMeta):
        super().__init__(config)
        self._ready = False
        self.settings = config.get_config(self.settings_cls) or self.settings_cls()
        self.app = config._application if isinstance(config._application, BaseHandler) else None
        self._mounts = {}

    def load_route(self, path: str):
        return (path or '').strip('/')

    def setup(self):
        if self._ready:
            return
        self.settings = self.config.get_config(self.settings_cls) or self.settings
        self.settings.setup(self.config)

        root_api = self.config.resolve()
        if self.config.root_url:
            url_pattern = rf'^{self.config.root_url}(\/.*)?$'
        else:
            url_pattern = root_api._get_route_pattern()

        self.add_api(
            root_api,
            route=url_pattern,
            asynchronous=self.asynchronous,
            top=bool(url_pattern)
        )
        self.setup_middlewares()
        self.apply_fork()
        # check wsgi application
        self._ready = True

    # def add_middleware(self):
    #     pass

    def setup_middlewares(self):
        func = self.middleware_func
        if not func:
            return

        if self.settings.django_settings and self.settings.module:
            if not hasattr(self.settings.module, func.__name__):
                setattr(self.settings.module, func.__name__, func)
                self.settings.merge_list_settings(
                    'MIDDLEWARE', [f'{self.settings.module_name}.{func.__name__}']
                )
                if self.app:
                    self.app.load_middleware()
        else:
            raise ValueError(f'setup django middleware failed: settings not loaded')

    @property
    def backend_views_empty(self) -> bool:
        if self._mounts:
            return False
        urls = getattr(self.settings.url_conf, self.URLPATTERNS, [])
        for url in urls:
            if isinstance(url, URLPattern):
                wrapped = getattr(url.callback, '__wrapped__', None)
                if wrapped and isinstance(wrapped, type) and issubclass(wrapped, API):
                    pass
                else:
                    return False
            else:
                return False
        return True

    @property
    def middleware_func(self):
        if not self.middlewares:
            return None

        def utilmeta_middleware(get_response):
            # One-time configuration and initialization.

            def func(django_request):
                # Code to be executed for each request before
                # the view (and later middleware) are called.
                response = None
                request = Request(self.request_adaptor_cls(django_request))
                for middleware in self.middlewares:
                    request = middleware.process_request(request) or request
                    if isinstance(request, Response):
                        response = request
                        break

                if response:
                    return self.response_adaptor_cls.reconstruct(response)

                _current_request.set(request)
                # fixme:
                # in production (uwsgi)
                # request.META might lost during log saving
                # result in the emptiness of ip_address and url
                django_response = get_response(django_request)
                _current_request.set(None)

                # Code to be executed for each request/response after
                # the view is called.

                response = _current_response.get(None)
                _current_response.set(None)
                if not isinstance(response, Response):
                    response = Response(
                        response=self.response_adaptor_cls(django_response),
                        request=request
                    )
                else:
                    if not response.adaptor:
                        response.adaptor = self.response_adaptor_cls(
                            django_response
                        )

                response_updated = False
                for middleware in self.middlewares:
                    _response = middleware.process_response(response)
                    if isinstance(_response, Response):
                        response = _response
                        response_updated = True

                if response_updated:
                    django_response = self.response_adaptor_cls.reconstruct(response)

                return django_response

            return func

        return utilmeta_middleware

    def check_application(self):
        wsgi_app = self.settings.wsgi_app
        if not wsgi_app:
            if self.config.production:
                raise ValueError(f'Django wsgi application not specified, you should use '
                                 f'{self.settings.wsgi_app_attr or "app"} = service.application() '
                                 f'in {self.settings.wsgi_module_ref or "your service file"}')
            else:
                wsgi_module = self.settings.wsgi_module
                if not wsgi_module:
                    if self.settings.wsgi_application:
                        raise ValueError(f'Invalid Django WSGI_APPLICATION: '
                                         f'{repr(self.settings.wsgi_application)}')
                    raise ValueError(f'Django WSGI_APPLICATION not specified')
                if not self.settings.wsgi_app_attr:
                    raise ValueError(f'Django WSGI_APPLICATION not specified or invalid:'
                                     f' {repr(self.settings.wsgi_application)}')
                warnings.warn('Django application not specified, auto-assigning, you should use '
                              f'{self.settings.wsgi_app_attr or "app"} = service.application() '
                              f'in {self.settings.wsgi_module_ref or "your service file"} at production')
                setattr(wsgi_module, self.settings.wsgi_app_attr, self.application())

    def mount(self, app, route: str):
        urls_attr = getattr(app, 'urls', None)
        if not urls_attr or not isinstance(urls_attr, (list, tuple)):
            raise TypeError('Invalid application to mount to django, anyone with "urls" attribute is supported, '
                            'such as NinjaAPI in django-ninja or DefaultRouter in django-rest-framework')
        if all(isinstance(pattern, URLPattern) for pattern in urls_attr):
            urls_attr = include((urls_attr, route.strip('/')))

        # to mount django-ninja app or django-rest-framework router
        urls = getattr(self.settings.url_conf, self.URLPATTERNS, [])
        urls.append(
            path(route.strip('/') + '/', urls_attr)
        )
        setattr(self.settings.url_conf, self.URLPATTERNS, urls)
        self._mounts[route] = app

    def adapt(self, api: 'API', route: str, asynchronous: bool = None):
        if asynchronous is None:
            asynchronous = self.default_asynchronous
        # func = self._get_api(api, asynchronous=asynchronous)
        # path = f'{route.strip("/")}/(.*)' if route.strip('/') else '(.*)'
        # return re_path(path, func)
        self.add_api(api, route=route, asynchronous=asynchronous)

    def add_api(self, utilmeta_api_class, route: str = '', asynchronous: bool = False, top: bool = False):
        api = self._get_api(utilmeta_api_class, asynchronous=asynchronous)
        urls = getattr(self.settings.url_conf, self.URLPATTERNS, [])
        find = False
        for url in urls:
            if isinstance(url, URLPattern):
                if str(url.pattern) == str(route):
                    wrapped = getattr(url.callback, '__wrapped__', None)
                    if wrapped:
                        if wrapped == utilmeta_api_class or wrapped.__qualname__ == utilmeta_api_class.__qualname__:
                            find = True
                            break
        if find:
            return
        api_path = re_path(route, api)
        if top:
            urls.insert(0, api_path)
        else:
            urls.append(api_path)
        setattr(self.settings.url_conf, self.URLPATTERNS, urls)

    def _get_api(self, utilmeta_api_class, asynchronous: bool = False):
        """
        Mount a API class
        make sure it is called after all your fastapi route is set
        """
        from utilmeta.core.api.base import API
        if not issubclass(utilmeta_api_class, API):
            raise TypeError(f'Invalid api class: {utilmeta_api_class}')

        if asynchronous:
            async def f(request, route: str = '', *args, **kwargs):
                req = None
                try:
                    req = _current_request.get(None)
                    route = self.load_route(route)

                    if not isinstance(req, Request):
                        req = Request(self.request_adaptor_cls(request, route, *args, **kwargs))
                    else:
                        req.adaptor.route = route
                        req.adaptor.request = request

                    root = utilmeta_api_class(req)
                    resp = await root()
                except Exception as e:
                    resp = getattr(utilmeta_api_class, 'response', Response)(error=e, request=req)
                _current_response.set(resp)
                return self.response_adaptor_cls.reconstruct(resp)
        else:
            def f(request, route: str = '', *args, **kwargs):
                req = None
                try:
                    req = _current_request.get(None)
                    route = self.load_route(route)

                    if not isinstance(req, Request):
                        req = Request(self.request_adaptor_cls(request, route, *args, **kwargs))
                    else:
                        req.adaptor.route = route
                        req.adaptor.request = request

                    root = utilmeta_api_class(req)
                    resp = root()
                except Exception as e:
                    resp = getattr(utilmeta_api_class, 'response', Response)(error=e, request=req)
                _current_response.set(resp)
                return self.response_adaptor_cls.reconstruct(resp)

        update_wrapper(f, utilmeta_api_class, updated=())
        f.csrf_exempt = True  # noqa
        # as this f() of RootAPI is the only callable return to set url
        # csrf_exempt must set to True or every result without token will be blocked
        return f

    def application(self):
        self.setup()
        if self.app:
            return self.app
        if self.asynchronous:
            from django.core.handlers.asgi import ASGIHandler
            self.app = ASGIHandler()
        else:
            from django.core.handlers.wsgi import WSGIHandler
            self.app = WSGIHandler()
        # return self.app
        return self.app

    def run(self):
        self.setup()
        self.check_application()

        if self.background:
            return

        self.config.startup()
        if self.asynchronous:
            try:
                from daphne.server import Server
            except ModuleNotFoundError:
                pass
            else:
                print('using [daphne] as asgi server')
                try:
                    Server(
                        application=self.application(),
                        endpoints=[self.daphne_endpoint],
                        server_name=self.config.name,
                    ).run()
                finally:
                    self.config.shutdown()
                return

            from utilmeta.utils import check_requirement
            check_requirement('uvicorn', install_when_require=True)
            import uvicorn
            print('using [uvicorn] as asgi server')
            try:
                uvicorn.run(
                    self.application(),
                    host=self.config.host or self.DEFAULT_HOST,
                    port=self.config.port,
                )
            finally:
                self.config.shutdown()
                return

        if self.config.production:
            server = 'asgi (like uvicorn/daphne)' if self.asynchronous else 'wsgi (like uwsgi/gunicorn)'
            raise ValueError(f'django in production cannot use service.run(), please use an {server} server')
        else:
            if self.asynchronous:
                raise ValueError(f'django debug runserver does not support asgi, please use an asgi server')
            try:
                self.runserver()
            finally:
                self.config.shutdown()
                return

    @property
    def location(self):
        return f'{self.config.host or self.DEFAULT_HOST}:{self.config.port}'

    @property
    def daphne_endpoint(self):
        return f"tcp:{self.config.port}:interface={self.config.host or self.DEFAULT_HOST}"

    def runserver(self):
        # debug server
        argv = [sys.argv[0], 'runserver', self.location]  # if len(sys.argv) == 1 else sys.argv
        # if 'runserver' in argv:
        if not self.config.auto_reload:
            argv.append('--noreload')
        execute_from_command_line(argv)

    @classmethod
    def get_drf_openapi(
        cls,
        title=None, url=None, description=None, version=None
    ):
        from rest_framework.schemas.openapi import SchemaGenerator
        generator = SchemaGenerator(title=title, url=url, description=description, version=version)

        def generator_func(service: 'UtilMeta'):
            return generator.get_schema(public=True)

        return generator_func

    @classmethod
    def get_django_ninja_openapi(cls):
        from ninja.openapi.schema import get_schema
        from ninja import NinjaAPI

        def generator_func(service: 'UtilMeta'):
            app = service.application()
            if isinstance(app, NinjaAPI):
                return get_schema(app)
            raise TypeError(f'Invalid application: {app} for django ninja. NinjaAPI() instance expected')

        return generator_func

    def generate(self, spec: str = 'openapi'):
        if spec == 'openapi':
            if self.settings.django_settings:
                if 'rest_framework' in self.settings.django_settings.INSTALLED_APPS:
                    # 1. try drf
                    from rest_framework.schemas.openapi import SchemaGenerator
                    generator = SchemaGenerator(
                        title=self.config.title,
                        description=self.config.description,
                        version=self.config.version
                    )

                    return generator.get_schema(public=True)

