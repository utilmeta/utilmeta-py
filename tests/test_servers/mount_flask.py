import time

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


from tests.config import make_live
server_thread = make_live(service)

# fixme: flask app must start at the main thread
# def test_mount_flask(server_thread):
#     with service.get_client(live=True) as client:
#         r1 = client.get('v1/hello')
#         assert r1.status == 200
#         assert r1.data == "<p>Hello, flask!</p>"


if __name__ == '__main__':
    service.run()
