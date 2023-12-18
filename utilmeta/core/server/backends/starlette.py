import starlette
from starlette.requests import Request
from starlette.applications import Starlette
from .base import ServerAdaptor
from utilmeta.core.response import Response
from utilmeta.core.request.backends.starlette import StarletteRequestAdaptor
from utilmeta.core.response.backends.starlette import StarletteResponseAdaptor


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
        self.app = self.application_cls(debug=not self.config.production)
        self._ready = False

    # def _monkey_patch(self):
    #     if not self.background and not self.config.production:
    #         # not self.background, which is only set in run()
    #         from utilmeta.patch import Patcher
    #         Patcher(*self.config.deploy.get_patches())

    @property
    def root_route(self):
        if not self.config.root_url:
            return ''
        return '/' + self.config.root_url.strip('/')

    def setup(self):
        # TODO: execute setup plugins
        # self._monkey_patch()
        if self._ready:
            return
        self.add_api(
            self.app,
            self.resolve(),
            asynchronous=self.asynchronous,
            route=self.root_route
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

    @classmethod
    def add_api(cls, app: Starlette, utilmeta_api_class, route: str = '', asynchronous: bool = False):
        """
        Mount a API class
        make sure it is called after all your fastapi route is set
        """
        from utilmeta.core.api.base import API
        if not isinstance(utilmeta_api_class, type) or not issubclass(utilmeta_api_class, API):
            raise TypeError(f'Invalid api class: {utilmeta_api_class}')
        # utilmeta_api_class: Type[API]
        if asynchronous:
            @app.route('%s/{path:path}' % route, methods=cls.HANDLED_METHODS)
            async def f(request: Request):
                try:
                    path = request.path_params['path']
                    resp = await utilmeta_api_class(
                        cls.request_adaptor_cls(request, path)
                    )()
                except Exception as e:
                    resp = getattr(utilmeta_api_class, 'response', Response)(error=e)
                return cls.response_adaptor_cls.reconstruct(resp)
        else:
            @app.route('%s/{path:path}' % route, methods=cls.HANDLED_METHODS)
            def f(request: Request):
                try:
                    path = request.path_params['path']
                    resp = utilmeta_api_class(
                        cls.request_adaptor_cls(request, path)
                    )()
                except Exception as e:
                    resp = getattr(utilmeta_api_class, 'response', Response)(error=e)
                return cls.response_adaptor_cls.reconstruct(resp)

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
