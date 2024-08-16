# /path/to/server.py
from sanic import Sanic
from sanic.response import text

app = Sanic("MyHelloWorldApp")


@app.get("/")
async def hello_world(request):
    return text("Hello, world.")


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


CalcAPI.__as__(app, route='/calc')

if __name__ == '__main__':
    app.run()

