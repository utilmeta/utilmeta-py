import os
import sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.dirname(__file__))

from sanic import Sanic
from sanic.response import text
Sanic._app_registry = {}

app = Sanic('MyTestApp')


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
    eager_migrate=True
).integrate(app, __name__)


@app.get("/sanic")
async def hello_world(request):
    return text("Hello, sanic")

if __name__ == '__main__':
    try:
        from pytest_cov.embed import cleanup_on_sigterm
    except ImportError:
        pass
    else:
        cleanup_on_sigterm()
    app.run(port=PORT, dev=True)
