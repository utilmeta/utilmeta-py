import inspect

import starlette
from starlette.requests import Request as StarletteRequest
from starlette.applications import Starlette
from starlette.concurrency import iterate_in_threadpool
from starlette.middleware.base import _StreamingResponse
from .base import ServerAdaptor
from utilmeta.core.response import Response
from utilmeta.core.request.backends.starlette import StarletteRequestAdaptor
from utilmeta.core.response.backends.starlette import StarletteResponseAdaptor
from utilmeta.core.api import API
from utilmeta.core.request import Request
from utilmeta.utils import HAS_BODY_METHODS, RequestType, exceptions
import contextvars
from typing import Optional
from urllib.parse import urlparse

_current_request = contextvars.ContextVar('_starlette.request')
# _current_response = contextvars.ContextVar('_starlette.response')
# starlette 's response may cross the context, so that cannot be picked


class StarletteServerAdaptor(ServerAdaptor):
    backend = starlette
    application_cls = Starlette  # can be inherit and replace with FastAPI
    request_adaptor_cls = StarletteRequestAdaptor
    response_adaptor_cls = StarletteResponseAdaptor
    default_asynchronous = True
    DEFAULT_PORT = 8000
    RECORD_RESPONSE_BODY_STATUS_GTE = 400
    RECORD_RESPONSE_BODY_LENGTH_LTE = 1024 ** 2
    RECORD_REQUEST_BODY_LENGTH_LTE = 1024 ** 2
    RECORD_REQUEST_BODY_TYPES = [
        RequestType.JSON, RequestType.XML, RequestType.APP_XML, RequestType.HTML,
        RequestType.FORM_DATA, RequestType.FORM_URLENCODED, RequestType.PLAIN
    ]

    DEFAULT_HOST = '127.0.0.1'
    HANDLED_METHODS = ["DELETE", "HEAD", "GET", "OPTIONS", "PATCH", "POST", "PUT"]

    def __init__(self, config):
        super().__init__(config=config)
        self.app = self.config._application if isinstance(self.config._application, self.application_cls) \
            else self.application_cls(debug=not self.config.production)
        self._ready = False
        self._mounts = {}

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
        self._mounts[route] = app

    def load_route(self, request: StarletteRequest):
        path = request.path_params.get('path') or request.url.path
        return super().load_route(path)

    @property
    def backend_views_empty(self) -> bool:
        if self._mounts:
            return False
        for val in self.app.routes:
            f = getattr(val, 'endpoint', None)
            if f:
                wrapped = getattr(f, '__wrapped__', None)
                if wrapped and isinstance(wrapped, type) and issubclass(wrapped, API):
                    pass
                else:
                    return False
        return True

    # def add_middleware(self):
    #     self.app.add_middleware()

    @property
    def production(self) -> bool:
        return not self.app.debug

    def setup_middlewares(self):
        if self.middlewares:
            from starlette.middleware.base import BaseHTTPMiddleware
            self.app.add_middleware(
                BaseHTTPMiddleware,     # noqa
                dispatch=self.get_middleware_func()
            )

    @classmethod
    async def get_response_body(cls, starlette_response: _StreamingResponse) -> bytes:
        response_body = [chunk async for chunk in starlette_response.body_iterator]
        starlette_response.body_iterator = iterate_in_threadpool(iter(response_body))
        return b''.join(response_body)

    def get_middleware_func(self):
        async def utilmeta_middleware(starlette_request: StarletteRequest, call_next):
            response = None
            starlette_response = None

            request = Request(self.request_adaptor_cls(starlette_request))
            for middleware in self.middlewares:
                res = middleware.process_request(request) or request
                if inspect.isawaitable(request):
                    res = await res
                if isinstance(res, Response):
                    response = res
                    break
                elif isinstance(res, Request):
                    request = res

            if response is None:
                if request.adaptor.request_method.lower() in HAS_BODY_METHODS:
                    if request.content_type in self.RECORD_REQUEST_BODY_TYPES and (
                            request.content_length or 0) <= self.RECORD_RESPONSE_BODY_LENGTH_LTE:
                        request.adaptor.body = await starlette_request.body()
                        # read the body here any way, the request will cache it
                        # and you cannot read it after response is generated

                _current_request.set(request)
                starlette_response: Optional[_StreamingResponse] = await call_next(starlette_request)
                _current_request.set(None)
                response = request.adaptor.get_context('response')
                # response = _current_response.get(None)
                # _current_response.set(None)

                if not isinstance(response, Response):
                    # from native starlette api
                    adaptor = self.response_adaptor_cls(
                        starlette_response
                    )
                    if starlette_response.status_code >= self.RECORD_RESPONSE_BODY_STATUS_GTE:
                        if (adaptor.content_length or 0) <= self.RECORD_RESPONSE_BODY_LENGTH_LTE:
                            body = await self.get_response_body(starlette_response)
                            starlette_response.body = body
                            # set body
                    response = Response(
                        response=adaptor,
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
            default=self.config.auto_created
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

    def add_api(self, app: Starlette, utilmeta_api_class, route: str = '',
                asynchronous: bool = False, default: bool = False):
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
            async def f(request: StarletteRequest, _default: bool = False):
                req = None
                try:
                    req = _current_request.get(None)
                    path = self.load_route(request)
                    if not isinstance(req, Request):
                        req = Request(self.request_adaptor_cls(request, path))
                    else:
                        req.adaptor.route = path
                        req.adaptor.request = request
                    resp = await utilmeta_api_class(
                        req
                    )()
                except Exception as e:
                    if _default:
                        if isinstance(e, exceptions.NotFound) and e.path:
                            raise
                    resp = getattr(utilmeta_api_class, 'response', Response)(error=e, request=req)
                if req:
                    req.adaptor.update_context(response=resp)
                return self.response_adaptor_cls.reconstruct(resp)
        else:
            # @app.route('%s/{path:path}' % route, methods=cls.HANDLED_METHODS)
            def f(request: StarletteRequest, _default: bool = False):
                req = None
                try:
                    req = _current_request.get(None)
                    path = self.load_route(request)
                    if not isinstance(req, Request):
                        req = Request(self.request_adaptor_cls(request, path))
                    else:
                        req.adaptor.route = path
                        req.adaptor.request = request
                    resp = utilmeta_api_class(
                        req
                    )()
                except Exception as e:
                    if _default:
                        if isinstance(e, exceptions.NotFound) and e.path:
                            raise
                    resp = getattr(utilmeta_api_class, 'response', Response)(error=e, request=req)
                if req:
                    req.adaptor.update_context(response=resp)
                return self.response_adaptor_cls.reconstruct(resp)
        f.__wrapped__ = utilmeta_api_class

        if default:
            original_default = app.router.default

            async def default_route(scope, receive, send):
                from starlette.requests import Request
                request = Request(scope, receive=receive, send=send)
                try:
                    response = f(request, True)
                    if inspect.isawaitable(response):
                        response = await response
                except exceptions.NotFound:
                    # if the root router cannot analyze, we fall back to the original default
                    return await original_default(scope, receive, send)
                await response(scope, receive, send)
            app.router.default = default_route
        else:
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
            from utilmeta.utils import check_requirement
            check_requirement('uvicorn', install_when_require=True)
            import uvicorn
            uvicorn.run(
                self.app,
                host=self.config.host or self.DEFAULT_HOST,
                port=self.config.port,
                **kwargs
            )
