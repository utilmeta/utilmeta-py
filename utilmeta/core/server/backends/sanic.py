import sanic
from sanic import Sanic
from utilmeta.core.request.backends.sanic import SanicRequestAdaptor
from utilmeta.core.response.backends.sanic import SanicResponseAdaptor
from utilmeta.core.response import Response
from utilmeta.core.request import Request
from .base import ServerAdaptor
from utilmeta.core.api import API
import contextvars

_current_request = contextvars.ContextVar('_sanic.request')
_current_response = contextvars.ContextVar('_sanic.response')


class SanicServerAdaptor(ServerAdaptor):
    backend = sanic
    request_adaptor_cls = SanicRequestAdaptor
    response_adaptor_cls = SanicResponseAdaptor
    application_cls = Sanic
    DEFAULT_NAME = 'sanic_application'
    default_asynchronous = True
    HANDLED_METHODS = ("DELETE", "HEAD", "GET", "OPTIONS", "PATCH", "POST", "PUT")

    def __init__(self, config):
        super().__init__(config)
        self.app = self.config._application if isinstance(self.config._application, self.application_cls) \
            else self.application_cls(self.config.name or self.DEFAULT_NAME)
        self._ready = False

    def application(self):
        self.setup()
        return self.app

    def adapt(self, api: 'API', route: str, asynchronous: bool = None):
        if asynchronous is None:
            asynchronous = self.default_asynchronous
        self.add_api(self.app, api, asynchronous=asynchronous, route=route)

    def on_request(self, sanic_request):
        response = None
        request = Request(self.request_adaptor_cls(sanic_request))

        for middleware in self.middlewares:
            request = middleware.process_request(request) or request
            if isinstance(request, Response):
                response = request
                break
        # -----------------------------------
        if response is not None:
            return self.response_adaptor_cls.reconstruct(response)

        _current_request.set(request)

    def on_response(self, sanic_request, sanic_response):
        response = _current_response.get(None)
        if not isinstance(response, Response):
            response = Response(
                response=self.response_adaptor_cls(
                    sanic_response
                ),
                request=Request(self.request_adaptor_cls(sanic_request))
            )
        else:
            if not response.adaptor:
                response.adaptor = self.response_adaptor_cls(
                    sanic_response
                )

        response_updated = False
        for middleware in self.middlewares:
            _response = middleware.process_response(response)
            if isinstance(_response, Response):
                response = _response
                response_updated = True

        if response_updated:
            # -----------------------------------
            sanic_response = self.response_adaptor_cls.reconstruct(response)

        _current_request.set(None)
        _current_response.set(None)
        return sanic_response

    def setup_middlewares(self):
        if self.middlewares:
            self.app.on_request(self.on_request)
            self.app.on_response(self.on_response)

    def setup(self):
        if self._ready:
            return
        self.add_api(
            self.app,
            self.resolve(),
            asynchronous=self.asynchronous
        )

        self.setup_middlewares()

        @self.app.after_server_start
        async def startup(*_):
            await self.config.startup()

        @self.app.after_server_stop
        async def shutdown(*_):
            await self.config.shutdown()

        self._ready = True

    def run(self, **kwargs):
        self.setup()
        self.app.run(
            host=self.config.host,
            port=self.config.port,
            debug=not self.config.production,
            **kwargs
        )

    def add_api(self, app: Sanic, utilmeta_api_class, route: str = '', asynchronous: bool = False):
        """
        Mount a API class
        make sure it is called after all your fastapi route is set
        """
        from utilmeta.core.api.base import API
        if not issubclass(utilmeta_api_class, API):
            raise TypeError(f'Invalid api class: {utilmeta_api_class}')

        if route and route.strip('/'):
            route = '/' + route.strip('/')
            prepend = route + '/'
        else:
            prepend = '/'

        if asynchronous:
            # @app.route(route, methods=self.HANDLED_METHODS, name='core_methods')
            @app.route('%s<path:path>' % prepend, methods=self.HANDLED_METHODS)
            async def f(request, path: str = ''):
                req = None
                try:
                    req = _current_request.get(None)
                    path = self.load_route(path)

                    if not isinstance(req, Request):
                        req = self.request_adaptor_cls(request, path)
                    else:
                        req.adaptor.route = path
                        req.adaptor.request = request

                    resp = await utilmeta_api_class(req)()
                except Exception as e:
                    resp = getattr(utilmeta_api_class, 'response', Response)(error=e, request=req)
                _current_response.set(resp)
                return self.response_adaptor_cls.reconstruct(resp)
        else:
            # @app.route(route, methods=self.HANDLED_METHODS, name='core_methods')
            @app.route('%s<path:path>' % prepend, methods=self.HANDLED_METHODS)
            def f(request, path: str = ''):
                req = None
                try:
                    req = _current_request.get(None)
                    path = self.load_route(path)

                    if not isinstance(req, Request):
                        req = self.request_adaptor_cls(request, path)
                    else:
                        req.adaptor.route = path
                        req.adaptor.request = request

                    resp = utilmeta_api_class(req)()
                except Exception as e:
                    resp = getattr(utilmeta_api_class, 'response', Response)(error=e, request=req)
                _current_response.set(resp)
                return self.response_adaptor_cls.reconstruct(resp)

        # app.route('%s<path:path>' % prepend, methods=self.HANDLED_METHODS, name='extend_path')(f)
        # app.route(route, methods=self.HANDLED_METHODS, name='core_methods')(f)
