import tornado
from tornado.web import RequestHandler, Application
from utilmeta.core.response import Response
from utilmeta.core.request.backends.tornado import TornadoServerRequestAdaptor
from .base import ServerAdaptor
import asyncio


class TornadoServerAdaptor(ServerAdaptor):
    backend = tornado
    request_adaptor_cls = TornadoServerRequestAdaptor
    application_cls = Application
    DEFAULT_PORT = 8000
    default_asynchronous = True

    def __init__(self, config):
        super().__init__(config)
        self.app = None

    def request_handler(self):
        request_adaptor_cls = self.request_adaptor_cls
        root_api = self.resolve()

        if self.asynchronous:
            class Handler(RequestHandler):
                async def get(self, *args, **kwargs):
                    return await self.handle(*args, **kwargs)

                async def put(self, *args, **kwargs):
                    return await self.handle(*args, **kwargs)

                async def post(self, *args, **kwargs):
                    return await self.handle(*args, **kwargs)

                async def patch(self, *args, **kwargs):
                    return await self.handle(*args, **kwargs)

                async def delete(self, *args, **kwargs):
                    return await self.handle(*args, **kwargs)

                async def head(self, *args, **kwargs):
                    return await self.handle(*args, **kwargs)

                async def options(self, *args, **kwargs):
                    return await self.handle(*args, **kwargs)

                async def handle(self, path: str):
                    try:
                        request = request_adaptor_cls(self.request, path)
                        response: Response = await root_api(request)()
                        if not isinstance(response, Response):
                            response = Response(response)
                    except Exception as e:
                        response = getattr(root_api, 'response', Response)(error=e)
                    self.write(response.prepare_body())
                    for key, value in response.prepare_headers(with_content_type=True):
                        self.add_header(key, value)
        else:
            class Handler(RequestHandler):
                def get(self, *args, **kwargs):
                    return self.handle(*args, **kwargs)

                def put(self, *args, **kwargs):
                    return self.handle(*args, **kwargs)

                def post(self, *args, **kwargs):
                    return self.handle(*args, **kwargs)

                def patch(self, *args, **kwargs):
                    return self.handle(*args, **kwargs)

                def delete(self, *args, **kwargs):
                    return self.handle(*args, **kwargs)

                def head(self, *args, **kwargs):
                    return self.handle(*args, **kwargs)

                def options(self, *args, **kwargs):
                    return self.handle(*args, **kwargs)

                def handle(self, path: str):
                    try:
                        request = request_adaptor_cls(self.request, path)
                        response: Response = root_api(request)()
                    except Exception as e:
                        response = getattr(root_api, 'response', Response)(error=e)
                    self.write(response.prepare_body())
                    for key, value in response.prepare_headers(with_content_type=True):
                        self.add_header(key, value)

        return Handler

    @property
    def root_pattern(self):
        if not self.config.root_url:
            return '/(.*)'
        return '/%s/(.*)' % self.config.root_url.strip('/')

    def application(self):
        return self.setup()

    async def main(self):
        app = self.setup()
        app.listen(self.config.port or self.DEFAULT_PORT)
        await self.config.startup()
        await asyncio.Event().wait()
        await self.config.shutdown()

    def setup(self):
        if self.app:
            return self.app
        self.app = self.application_cls([
            (self.root_pattern, self.request_handler())
        ])
        return self.app

    def run(self):
        asyncio.run(self.main())
