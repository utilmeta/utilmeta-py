import starlette
from starlette.requests import Request
from starlette.applications import Starlette
# from starlette.routing import Route
from .base import ServerAdaptor
from utilmeta.core.response import Response
from utilmeta.core.request.backends.starlette import StarletteRequestAdaptor
from utilmeta.core.response.backends.starlette import StarletteResponseAdaptor
from utilmeta.core.api import API


class StarletteServerAdaptor(ServerAdaptor):
    backend = starlette
    application_cls = Starlette  # can be inherit and replace with FastAPI
    request_adaptor_cls = StarletteRequestAdaptor
    response_adaptor_cls = StarletteResponseAdaptor
    default_asynchronous = True
    DEFAULT_PORT = 8000
    DEFAULT_HOST = '127.0.0.1'
    HANDLED_METHODS = ["DELETE", "HEAD", "GET", "OPTIONS", "PATCH", "POST", "PUT"]

    def __init__(self, config):
        super().__init__(config=config)
        self.app = self.config._application or self.application_cls(debug=not self.config.production)
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
            async def f(request: Request):
                try:
                    path = self.load_route(request.path_params['path'])
                    resp = await utilmeta_api_class(
                        self.request_adaptor_cls(request, path)
                    )()
                except Exception as e:
                    resp = getattr(utilmeta_api_class, 'response', Response)(error=e)
                return self.response_adaptor_cls.reconstruct(resp)
        else:
            # @app.route('%s/{path:path}' % route, methods=cls.HANDLED_METHODS)
            def f(request: Request):
                try:
                    path = self.load_route(request.path_params['path'])
                    resp = utilmeta_api_class(
                        self.request_adaptor_cls(request, path)
                    )()
                except Exception as e:
                    resp = getattr(utilmeta_api_class, 'response', Response)(error=e)
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
                port=self.config.port or self.DEFAULT_PORT,
                **kwargs
            )
