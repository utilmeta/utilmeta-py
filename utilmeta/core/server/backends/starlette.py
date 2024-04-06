import inspect

import starlette
from starlette.requests import Request as StarletteRequest
from starlette.applications import Starlette
from .base import ServerAdaptor
from utilmeta.core.response import Response
from utilmeta.core.request.backends.starlette import StarletteRequestAdaptor
from utilmeta.core.response.backends.starlette import StarletteResponseAdaptor
from utilmeta.core.api import API
from utilmeta.core.request import Request
import contextvars

_current_request = contextvars.ContextVar('_starlette.request')


class StarletteServerAdaptor(ServerAdaptor):
    backend = starlette
    application_cls = Starlette  # can be inherit and replace with FastAPI
    request_adaptor_cls = StarletteRequestAdaptor
    response_adaptor_cls = StarletteResponseAdaptor
    default_asynchronous = True
    DEFAULT_PORT = 8000
    DEFAULT_HOST = '127.0.0.1'
    HANDLED_METHODS = ["DELETE", "HEAD", "GET", "OPTIONS", "PATCH", "POST", "PUT"]

    # REQUEST_ATTR = '_utilmeta_request'
    RESPONSE_ATTR = '_utilmeta_response'

    def __init__(self, config):
        super().__init__(config=config)
        self.app = self.config._application if isinstance(self.config._application, self.application_cls) \
            else self.application_cls(debug=not self.config.production)
        self._ready = False

    def adapt(self, api: 'API', route: str, asynchronous: bool = None):
        if asynchronous is None:
            asynchronous = self.default_asynchronous
        self.add_api(self.app, api, asynchronous=asynchronous, route=route)

    def mount(self, app, route: str):
        if not self.is_asgi(app):
            from starlette.middleware.wsgi import WSGIMiddleware
            # todo: fix deprecated
            app = WSGIMiddleware(app)
        self.app.mount(route, app)

    # def add_middleware(self):
    #     self.app.add_middleware()

    def setup_middlewares(self):
        if self.middlewares:
            from starlette.middleware.base import BaseHTTPMiddleware
            self.app.add_middleware(
                BaseHTTPMiddleware,     # noqa
                dispatch=self.get_middleware_func()
            )

    def get_middleware_func(self):
        async def utilmeta_middleware(starlette_request: StarletteRequest, call_next):
            response = None
            starlette_response = None
            request = Request(self.request_adaptor_cls(starlette_request))
            for middleware in self.middlewares:
                request = middleware.process_request(request) or request
                if inspect.isawaitable(request):
                    request = await request
                if isinstance(request, Response):
                    response = request
                    break

            if response is None:
                _current_request.set(request)
                starlette_response = await call_next(starlette_request)
                _current_request.set(None)
                response = getattr(starlette_response, self.RESPONSE_ATTR, None)
                if not isinstance(response, Response):
                    response = Response(
                        response=self.response_adaptor_cls(
                            starlette_response
                        ),
                        request=request
                    )
                else:
                    if not response.adaptor:
                        response.adaptor = self.response_adaptor_cls(
                            starlette_response
                        )

            response_updated = False
            for middleware in self.middlewares:
                _response = middleware.process_response(response)
                if inspect.isawaitable(_response):
                    _response = await _response
                if isinstance(_response, Response):
                    response = _response
                    response_updated = True

            if not starlette_response or response_updated:
                starlette_response = self.response_adaptor_cls.reconstruct(response)

            return starlette_response

        return utilmeta_middleware

    def setup(self):
        # TODO: execute setup plugins
        # self._monkey_patch()
        if self._ready:
            return
        self.add_api(
            self.app,
            self.resolve(),
            asynchronous=self.asynchronous,
        )

        self.setup_middlewares()

        if self.asynchronous:
            @self.app.on_event('startup')
            async def on_startup():
                await self.config.startup()

            @self.app.on_event('shutdown')
            async def on_shutdown():
                await self.config.shutdown()
        else:
            @self.app.on_event('startup')
            def on_startup():
                self.config.startup()

            @self.app.on_event('shutdown')
            def on_shutdown():
                self.config.shutdown()

        self._ready = True

    def add_wsgi(self):
        pass

    def add_api(self, app: Starlette, utilmeta_api_class, route: str = '', asynchronous: bool = False):
        """
        Mount a API class
        make sure it is called after all your fastapi route is set
        """
        from utilmeta.core.api.base import API
        if not isinstance(utilmeta_api_class, type) or not issubclass(utilmeta_api_class, API):
            raise TypeError(f'Invalid api class: {utilmeta_api_class}')
        if route and route.strip('/'):
            route = '/' + route.strip('/') + '/'
        else:
            route = '/'

        # utilmeta_api_class: Type[API]
        if asynchronous:
            # @app.route('%s/{path:path}' % route, methods=cls.HANDLED_METHODS)
            async def f(request: StarletteRequest):
                req = None
                try:
                    req = _current_request.get(None)
                    path = self.load_route(request.path_params['path'])
                    if not isinstance(req, Request):
                        req = self.request_adaptor_cls(request, path)
                    else:
                        req.adaptor.route = path
                        req.adaptor.request = request
                    resp = await utilmeta_api_class(
                        req
                    )()
                except Exception as e:
                    resp = getattr(utilmeta_api_class, 'response', Response)(error=e, request=req)
                return self.response_adaptor_cls.reconstruct(resp)
        else:
            # @app.route('%s/{path:path}' % route, methods=cls.HANDLED_METHODS)
            def f(request: StarletteRequest):
                req = None
                try:
                    req = _current_request.get(None)
                    path = self.load_route(request.path_params['path'])
                    if not isinstance(req, Request):
                        req = self.request_adaptor_cls(request, path)
                    else:
                        req.adaptor.route = path
                        req.adaptor.request = request
                    resp = utilmeta_api_class(
                        req
                    )()
                except Exception as e:
                    resp = getattr(utilmeta_api_class, 'response', Response)(error=e, request=req)
                return self.response_adaptor_cls.reconstruct(resp)

        app.add_route(
            path='%s{path:path}' % route,
            route=f,
            methods=self.HANDLED_METHODS
        )

    def application(self):
        self.setup()
        return self.app

    def run(self, **kwargs):
        self.setup()
        if self.background:
            pass
        else:
            import uvicorn
            uvicorn.run(
                self.app,
                host=self.config.host or self.DEFAULT_HOST,
                port=self.config.port,
                **kwargs
            )
