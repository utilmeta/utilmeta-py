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
    Operations(
        route='v1/ops',
        database=Operations.Database(
            name='operations_db',
            engine='sqlite3'
        ),
        base_url=f'http://127.0.0.1:{PORT}',
        eager=True
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
    asyncio.run(main())