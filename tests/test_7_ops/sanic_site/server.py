from sanic import Sanic
from sanic.response import text

app = Sanic('MyTestApp')


@app.get("/sanic")
async def hello_world(request):
    return text("Hello, world.")

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

from utilmeta.ops import Operations
PORT = 9094

Operations(
    route='ops',
    database=Operations.Database(
        name='operations_db',
        engine='sqlite3'
    ),
    base_url=f'http://127.0.0.1:{PORT}',
    eager=True
).integrate(app, __name__)

if __name__ == '__main__':
    app.run(port=PORT, dev=True)