import tornado
from tornado.web import RequestHandler, Application
from utilmeta.core.response import Response
from utilmeta.core.request import Request
from utilmeta.core.request.backends.tornado import TornadoServerRequestAdaptor
from .base import ServerAdaptor
import asyncio
from utilmeta.core.api import API
from typing import Optional


class TornadoServerAdaptor(ServerAdaptor):
    backend = tornado
    request_adaptor_cls = TornadoServerRequestAdaptor
    application_cls = Application
    DEFAULT_PORT = 8000
    default_asynchronous = True

    def __init__(self, config):
        super().__init__(config)
        self.app = self.config._application if isinstance(self.config._application, self.application_cls) else None

    def adapt(self, api: 'API', route: str, asynchronous: bool = None):
        if asynchronous is None:
            asynchronous = self.default_asynchronous
        func = self.get_request_handler(api, asynchronous=asynchronous, append_slash=True)
        path = f'/{route.strip("/")}/(.*)' if route.strip('/') else '(.*)'
        return path, func
        # todo: support add APIs to application

    def get_request_handler(self, utilmeta_api_class, asynchronous: bool = False, append_slash: bool = False):
        request_adaptor_cls = self.request_adaptor_cls
        service = self

        if append_slash:
            decorator = tornado.web.addslash
        else:
            def decorator(f):
                return f

        if asynchronous:
            class Handler(RequestHandler):
                @decorator
                async def get(self, *args, **kwargs):
                    return await self.handle(*args, **kwargs)

                @decorator
                async def put(self, *args, **kwargs):
                    return await self.handle(*args, **kwargs)

                @decorator
                async def post(self, *args, **kwargs):
                    return await self.handle(*args, **kwargs)

                @decorator
                async def patch(self, *args, **kwargs):
                    return await self.handle(*args, **kwargs)

                @decorator
                async def delete(self, *args, **kwargs):
                    return await self.handle(*args, **kwargs)

                @decorator
                async def head(self, *args, **kwargs):
                    return await self.handle(*args, **kwargs)

                @decorator
                async def options(self, *args, **kwargs):
                    return await self.handle(*args, **kwargs)

                async def handle(self, path: str):
                    request = None
                    try:
                        path = service.load_route(path)
                        request = Request(request_adaptor_cls(self.request, path))
                        response: Optional[Response] = None

                        for middleware in service.middlewares:
                            request = middleware.process_request(request) or request
                            if isinstance(request, Response):
                                response = request
                                break

                        if response is None:
                            response: Response = await utilmeta_api_class(request)()
                        if not isinstance(response, Response):
                            response = Response(response=response, request=request)
                    except Exception as e:
                        response = getattr(utilmeta_api_class, 'response', Response)(error=e, request=request)

                    for middleware in service.middlewares:
                        _response = middleware.process_response(response)
                        if isinstance(_response, Response):
                            response = _response

                    self.set_status(response.status, reason=response.reason)
                    for key, value in response.prepare_headers(with_content_type=True):
                        self.set_header(key, value)
                    if response.status in (204, 304) or (100 <= response.status < 200):
                        return
                    body = response.prepare_body()
                    self.write(body)
        else:
            class Handler(RequestHandler):
                @decorator
                def get(self, *args, **kwargs):
                    return self.handle(*args, **kwargs)

                @decorator
                def put(self, *args, **kwargs):
                    return self.handle(*args, **kwargs)

                @decorator
                def post(self, *args, **kwargs):
                    return self.handle(*args, **kwargs)

                @decorator
                def patch(self, *args, **kwargs):
                    return self.handle(*args, **kwargs)

                @decorator
                def delete(self, *args, **kwargs):
                    return self.handle(*args, **kwargs)

                @decorator
                def head(self, *args, **kwargs):
                    return self.handle(*args, **kwargs)

                @decorator
                def options(self, *args, **kwargs):
                    return self.handle(*args, **kwargs)

                def handle(self, path: str):
                    request = None
                    try:
                        path = service.load_route(path)
                        request = Request(request_adaptor_cls(self.request, path))
                        response: Optional[Response] = None

                        for middleware in service.middlewares:
                            request = middleware.process_request(request) or request
                            if isinstance(request, Response):
                                response = request
                                break

                        if response is None:
                            response: Response = utilmeta_api_class(request)()
                        if not isinstance(response, Response):
                            response = Response(response=response, request=request)
                    except Exception as e:
                        response = getattr(utilmeta_api_class, 'response', Response)(error=e, request=request)

                    for middleware in service.middlewares:
                        _response = middleware.process_response(response) or response
                        if isinstance(_response, Response):
                            response = _response

                    self.set_status(response.status, reason=response.reason)
                    for key, value in response.prepare_headers(with_content_type=True):
                        self.set_header(key, value)

                    if response.status in (204, 304) or (100 <= response.status < 200):
                        return
                    body = response.prepare_body()
                    self.write(body)

        return Handler

    @property
    def request_handler(self):
        return self.get_request_handler(
            self.resolve(),
            asynchronous=self.asynchronous
        )

    def application(self):
        return self.setup()

    async def main(self):
        app = self.setup()
        app.listen(self.config.port)
        await self.config.startup()
        try:
            await asyncio.Event().wait()
        finally:
            await self.config.shutdown()

    def setup(self):
        if self.app:
            return self.app
        self.app = self.application_cls([
            ('(.*)', self.request_handler)
        ])
        return self.app

    def run(self):
        asyncio.run(self.main())
