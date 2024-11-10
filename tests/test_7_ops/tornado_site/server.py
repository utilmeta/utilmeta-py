import asyncio
import tornado


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, world")


def make_app():
    application = tornado.web.Application([
        (r"/", MainHandler),
    ])

    from utilmeta.ops import Operations
    import os
    Operations(
        route='v1/ops',
        database=Operations.Database(
            name=os.path.join(os.path.dirname(__file__), 'operations_db'),
            engine='sqlite3'
        ),
        secure_only=False,
        trusted_hosts=['127.0.0.1'],
        base_url='http://127.0.0.1:7803',
    ).integrate(application, __name__)
    return application


app = make_app()


async def main():
    app.listen(7803)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
