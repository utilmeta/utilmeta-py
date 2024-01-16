from flask import Flask

app = Flask(__name__)


@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"


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
