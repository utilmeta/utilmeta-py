from flask import Flask

app = Flask(__name__)


@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"


@app.route("/flask")
def hello_flask():
    return "<p>Hello, Flask!</p>"


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

Operations(
    route='v1/ops',
    database=Operations.database(
        name='db_ops',
        engine='sqlite3'
    ),
    secure_only=False,
    trusted_hosts=['127.0.0.1']
).integrate(app, __name__)

if __name__ == '__main__':
    app.run()
