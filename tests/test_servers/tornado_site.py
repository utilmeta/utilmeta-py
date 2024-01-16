import asyncio
import tornado


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, world")


from utilmeta.core import api, response


class CalcAPI(api.API):
    class response(response.Response):
        result_key = 'data'
        message_key = 'msg'

    @api.get
    def add(self, a: int, b: int) -> int:
        return a + b

    def get(self):
        return self.request.path


def make_app():
    return tornado.web.Application([
        CalcAPI.__as__(tornado, route='/calc'),
        (r"/", MainHandler),
    ])


async def main():
    app = make_app()
    app.listen(8888)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
