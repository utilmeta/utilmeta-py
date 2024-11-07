from sanic import Sanic
from sanic.response import text

app = Sanic('MyTestApp')


@app.get("/")
async def hello_world(request):
    return text("Hello, world.")

# from utilmeta.core import api, response
#
#
# class CalcAPI(api.API):
#     class response(response.Response):
#         result_key = 'data'
#         message_key = 'msg'
#
#     @api.get
#     def add(self, a: int, b: int) -> int:
#         return a + b
#
#     def get(self):
#         return self.request.path
#
#
# CalcAPI.__as__(app, route='/calc')
from utilmeta.ops import Operations
import os
Operations(
    route='v1/ops',
    database=Operations.Database(
        name=os.path.join(os.path.dirname(__file__), 'operations_db'),
        engine='sqlite3'
    ),
    secure_only=False,
    trusted_hosts=['127.0.0.1']
).integrate(app, __name__)

if __name__ == '__main__':
    app.run()
