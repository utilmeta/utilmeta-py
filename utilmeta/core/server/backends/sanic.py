import sanic
from sanic import Sanic
from utilmeta.core.request.backends.sanic import SanicRequestAdaptor
from utilmeta.core.response.backends.sanic import SanicResponseAdaptor
from utilmeta.core.response import Response
from .base import ServerAdaptor
from utilmeta.core.api import API


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
        self.app = self.config._application or self.application_cls(self.config.name or self.DEFAULT_NAME)
        self._ready = False

    def application(self):
        self.setup()
        return self.app

    def adapt(self, api: 'API', route: str, asynchronous: bool = None):
        if asynchronous is None:
            asynchronous = self.default_asynchronous
        self.add_api(self.app, api, asynchronous=asynchronous, route=route)

    def setup(self):
        if self._ready:
            return
        self.add_api(
            self.app,
            self.resolve(),
            asynchronous=self.asynchronous
        )

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
            prepend = route = '/'

        if asynchronous:
            # @app.route(route, methods=self.HANDLED_METHODS, name='core_methods')
            @app.route('%s<path:path>' % prepend, methods=self.HANDLED_METHODS)
            async def f(request, path: str = ''):
                try:
                    path = self.load_route(path)
                    resp = await utilmeta_api_class(
                        self.request_adaptor_cls(request, path)
                    )()
                except Exception as e:
                    resp = getattr(utilmeta_api_class, 'response', Response)(error=e)
                return self.response_adaptor_cls.reconstruct(resp)
        else:
            # @app.route(route, methods=self.HANDLED_METHODS, name='core_methods')
            @app.route('%s<path:path>' % prepend, methods=self.HANDLED_METHODS)
            def f(request, path: str = ''):
                try:
                    path = self.load_route(path)
                    resp = utilmeta_api_class(
                        self.request_adaptor_cls(request, path)
                    )()
                except Exception as e:
                    resp = getattr(utilmeta_api_class, 'response', Response)(error=e)
                return self.response_adaptor_cls.reconstruct(resp)

        # app.route('%s<path:path>' % prepend, methods=self.HANDLED_METHODS, name='extend_path')(f)
        # app.route(route, methods=self.HANDLED_METHODS, name='core_methods')(f)
