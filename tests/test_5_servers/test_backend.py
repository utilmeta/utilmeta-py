from utilmeta import UtilMeta
from utilmeta.core import api, request, response, file
from utype import Schema, Field
from typing import Tuple
from utype.types import *


class RootAPI(api.API):
    x_user_id: str = request.HeaderParam('X-user-ID', default=None)  # API param
    sessionid: str = request.CookieParam(default=None)  # API param

    class response(response.Response):
        result_key = "result"
        state_key = "state"
        message_key = "msg"
        count_key = "count"

        class headers(Schema):
            path_mark: str = Field(alias='Path-Mark', default=None)

    @api.post("{category}")
    def multipart(self,
                  category: str = request.SlugPathParam,
                  q: int = None,
                  images: List[file.File] = request.BodyParam,
                  name: str = request.BodyParam,
                  test_header: str = request.HeaderParam('X-Test-Header')
                  ):
        return [category, q, len(images), name, test_header]

    @api.get("doc/{category}/{page}")
    async def get_doc(self,
                      category: str,
                      page: int = 1,
                      q: str = None,
                      secs: float = 0.01,
                      host: str = request.HeaderParam(default=None)
                      ) -> Tuple[str, int, str, str, float]:
        import asyncio
        await asyncio.sleep(secs)
        return category, page, q, host, secs


class TestServers:
    def test_backends(self):
        import flask
        import sanic
        import django
        import fastapi
        import starlette
        import tornado
        from tests.server.server import service
        for backend in [
            django,
            flask,
            starlette,
            fastapi,
            tornado,
            sanic
        ]:
            service.set_backend(backend)
            service.application()

    def test_adapt_django(self):
        pass

    def test_adapt_flask(self):
        pass

    def test_adapt_starlette(self):
        pass

    def test_adapt_sanic(self):
        pass

    def test_adapt_tornado(self):
        pass
