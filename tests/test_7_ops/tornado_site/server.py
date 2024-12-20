import os
import sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.dirname(__file__))

import asyncio
import tornado


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, world")


PORT = 9095


def make_app():
    application = tornado.web.Application([
        (r"/tornado", MainHandler),
    ])

    from utilmeta.ops import Operations
    from tests.conftest import get_operations_db
    Operations(
        route='v1/ops',
        database=get_operations_db(),
        base_url=f'http://127.0.0.1:{PORT}',
        eager_migrate=True
    ).integrate(application, __name__)
    return application


app = make_app()

from utilmeta.core import api, response


@api.CORS(allow_origin='*')
class CalcAPI(api.API):
    class response(response.Response):
        result_key = 'data'
        message_key = 'msg'

    @api.get
    def add(self, a: int, b: int) -> int:
        return a + b

    def get(self):
        return self.request.path


CalcAPI.__as__(app, route='/calc')


async def main():
    app.listen(PORT)
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        from pytest_cov.embed import cleanup_on_sigterm
    except ImportError:
        pass
    else:
        cleanup_on_sigterm()
    asyncio.run(main())
