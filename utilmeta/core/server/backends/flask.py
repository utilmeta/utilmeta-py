import flask
from flask import Flask
from utilmeta.core.request.backends.werkzeug import WerkzeugRequestAdaptor
from utilmeta.core.response.backends.werkzeug import WerkzeugResponseAdaptor
from utilmeta.core.response import Response
from .base import ServerAdaptor


class FlaskServerAdaptor(ServerAdaptor):
    backend = flask
    request_adaptor_cls = WerkzeugRequestAdaptor
    response_adaptor_cls = WerkzeugResponseAdaptor
    application_cls = Flask
    default_asynchronous = False
    HANDLED_METHODS = ("DELETE", "HEAD", "GET", "OPTIONS", "PATCH", "POST", "PUT")
    DEFAULT_PORT = 8000
    DEFAULT_HOST = '127.0.0.1'

    def __init__(self, config):
        super().__init__(config)
        self.app = self.application_cls(self.config.module_name)
        self._ready = False

    def application(self):
        self.setup()
        return self.app

    @property
    def root_route(self):
        if not self.config.root_url:
            return ''
        return '/' + self.config.root_url.strip('/')

    def setup(self):
        if self._ready:
            return
        self.add_api(
            self.app,
            self.resolve(),
            route=self.root_route,
            asynchronous=self.asynchronous
        )

        # @self.app.after_server_start
        # async def startup(*_):
        #     await self.config.startup()
        #
        # @self.app.before_server_stop
        # async def shutdown(*_):
        #     await self.config.shutdown()

        self._ready = True

    def run(self, **kwargs):
        self.setup()
        self.app.run(
            host=self.config.host or self.DEFAULT_HOST,
            port=self.config.port or self.DEFAULT_PORT,
            debug=not self.config.production,
            **kwargs
        )

    @classmethod
    def add_api(cls, app: Flask, utilmeta_api_class, route: str = '', asynchronous: bool = False):
        """
        Mount a API class
        make sure it is called after all your fastapi route is set
        """
        from utilmeta.core.api.base import API
        if not issubclass(utilmeta_api_class, API):
            raise TypeError(f'Invalid api class: {utilmeta_api_class}')

        if asynchronous:
            @app.route('%s/<path:path>' % route, methods=cls.HANDLED_METHODS)
            async def f(path: str):
                from flask import request
                try:
                    resp = await utilmeta_api_class(
                        cls.request_adaptor_cls(request, path)
                    )()
                except Exception as e:
                    resp = getattr(utilmeta_api_class, 'response', Response)(error=e)
                return cls.response_adaptor_cls.reconstruct(resp)
        else:
            @app.route('%s/<path:path>' % route, methods=cls.HANDLED_METHODS)
            def f(path: str):
                from flask import request
                try:
                    resp = utilmeta_api_class(
                        cls.request_adaptor_cls(request, path)
                    )()
                except Exception as e:
                    resp = getattr(utilmeta_api_class, 'response', Response)(error=e)
                return cls.response_adaptor_cls.reconstruct(resp)
