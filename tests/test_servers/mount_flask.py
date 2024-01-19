from flask import Flask
from utilmeta import UtilMeta
from utilmeta.core import api, response

flask_app = Flask(__name__)


class RootAPI(api.API):
    class response(response.Response):
        result_key = 'data'
        message_key = 'error'

    @api.get
    def hello(self):
        return 'Hello, UtilMeta!'


service = UtilMeta(
    __name__,
    name='mount_flask',
    backend=flask_app,
    api=RootAPI,
    route='/api'
)


@flask_app.route("/v1/hello")
def hello_world():
    return "<p>Hello, flask!</p>"


if __name__ == '__main__':
    service.run()
