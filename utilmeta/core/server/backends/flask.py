import flask
from flask import Flask
from utilmeta.core.request.backends.werkzeug import WerkzeugRequestAdaptor
from utilmeta.core.response.backends.werkzeug import WerkzeugResponseAdaptor
from utilmeta.core.response import Response
from utilmeta.core.request import Request
from .base import ServerAdaptor
from utilmeta.core.api import API
import sys
import contextvars

_current_request = contextvars.ContextVar('_flask.request')
_current_response = contextvars.ContextVar('_flask.response')


class FlaskServerAdaptor(ServerAdaptor):
    backend = flask
    request_adaptor_cls = WerkzeugRequestAdaptor
    response_adaptor_cls = WerkzeugResponseAdaptor
    application_cls = Flask
    default_asynchronous = False
    HANDLED_METHODS = ("DELETE", "HEAD", "GET", "OPTIONS", "PATCH", "POST", "PUT")
    DEFAULT_HOST = '127.0.0.1'
    DEFAULT_PORT = 5000

    # REQUEST_ATTR = '_utilmeta_request'
    # RESPONSE_ATTR = '_utilmeta_response'

    def __init__(self, config):
        super().__init__(config)
        self.app = self.config._application if isinstance(self.config._application, self.application_cls) \
            else self.application_cls(self.config.module_name)
        self._ready = False

    # def init_application(self):
    #     return self.config._application if isinstance(self.config._application, self.application_cls) \
    #         else self.application_cls(self.config.module_name)

    def adapt(self, api: 'API', route: str, asynchronous: bool = None):
        if asynchronous is None:
            asynchronous = self.default_asynchronous
        self.add_api(self.app, api, asynchronous=asynchronous, route=route)

    def application(self):
        self.setup()
        return self.app

    def setup_middlewares(self):
        if self.middlewares:
            self.app.wsgi_app = self.wsgi_app

    def setup(self):
        if self._ready:
            return
        self.add_api(
            self.app,
            self.resolve(),
            asynchronous=self.asynchronous
        )

        self.setup_middlewares()
        self.apply_fork()

        self._ready = True

    def run(self, **kwargs):
        self.setup()
        self.config.startup()
        try:
            self.app.run(
                host=self.config.host or self.DEFAULT_HOST,
                port=self.config.port,
                debug=not self.config.production,
                **kwargs
            )
        finally:
            self.config.shutdown()

    @property
    def backend_views_empty(self) -> bool:
        for val in self.app.view_functions.values():
            wrapped = getattr(val, '__wrapped__', None)
            if wrapped and isinstance(wrapped, type) and issubclass(wrapped, API):
                pass
            else:
                return False
        return True

    def add_api(self, app: Flask, utilmeta_api_class, route: str = '', asynchronous: bool = False):
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
            @app.route(route, defaults={'path': ''}, methods=self.HANDLED_METHODS)
            @app.route('%s<path:path>' % prepend, methods=self.HANDLED_METHODS)
            async def f(path: str):
                from flask import request
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
            @app.route(route, defaults={'path': ''}, methods=self.HANDLED_METHODS)
            @app.route('%s<path:path>' % prepend, methods=self.HANDLED_METHODS)
            def f(path: str):
                from flask import request
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
        f.__wrapped__ = utilmeta_api_class
        return f

    def wsgi_app(self, environ: dict, start_response):
        """The actual WSGI application. This is not implemented in
        :meth:`__call__` so that middlewares can be applied without
        losing a reference to the app object. Instead of doing this::

            app = MyMiddleware(app)

        It's a better idea to do this instead::

            app.wsgi_app = MyMiddleware(app.wsgi_app)

        Then you still have the original application object around and
        can continue to call methods on it.

        .. versionchanged:: 0.7
            Teardown events for the request and app contexts are called
            even if an unhandled error occurs. Other events may not be
            called depending on when an error occurs during dispatch.
            See :ref:`callbacks-and-errors`.

        :param environ: A WSGI environment.
        :param start_response: A callable accepting a status code,
            a list of headers, and an optional exception context to
            start the response.
        """
        ctx = self.app.request_context(environ)
        error = None
        request = None
        flask_response = None
        try:
            try:
                ctx.push()
                from flask import request as flask_request
                # -----------------------
                response = None
                request = Request(self.request_adaptor_cls(flask_request))
                _current_request.set(request)

                for middleware in self.middlewares:
                    request = middleware.process_request(request) or request
                    if isinstance(request, Response):
                        response = request
                        break
                # -----------------------------------
                if response is None:
                    flask_response = self.app.full_dispatch_request()
                    _current_request.set(None)
                    response = _current_response.get(None)
                    _current_response.set(None)
                    if not isinstance(response, Response):
                        response = Response(
                            response=self.response_adaptor_cls(
                                flask_response
                            ),
                            request=request
                        )
                    else:
                        if not response.adaptor:
                            response.adaptor = self.response_adaptor_cls(
                                flask_response
                            )

            except Exception as e:
                error = e
                flask_response = self.app.handle_exception(e)
                response = Response(
                    response=self.response_adaptor_cls(
                        flask_response
                    ),
                    error=e,
                    request=request
                )
            except:  # noqa: B001
                error = sys.exc_info()[1]
                raise

            response_updated = False
            for middleware in self.middlewares:
                _response = middleware.process_response(response)
                if isinstance(_response, Response):
                    response = _response
                    response_updated = True

            if not flask_response or response_updated:
                flask_response = self.response_adaptor_cls.reconstruct(response)

            return flask_response(environ, start_response)
        finally:
            if "werkzeug.debug.preserve_context" in environ:
                from flask.app import _cv_app, _cv_request
                environ["werkzeug.debug.preserve_context"](_cv_app.get())
                environ["werkzeug.debug.preserve_context"](_cv_request.get())

            if error is not None and self.app.should_ignore_error(error):
                error = None
            ctx.pop(error)
