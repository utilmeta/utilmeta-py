from sanic import Sanic, text

sanic_app = Sanic('demo')


@sanic_app.get("/v1/hello")
def hello(request):
    return text("<p>Hello, sanic!</p>")


from utilmeta import UtilMeta
from utilmeta.core import api, response


class RootAPI(api.API):
    class response(response.Response):
        result_key = 'data'
        message_key = 'error'

    @api.get
    def hello(self):
        return 'Hello, UtilMeta!'


service = UtilMeta(
    __name__,
    name='test',
    backend=sanic_app,
    api=RootAPI,
    route='/api'
)

app = service.application()

if __name__ == '__main__':
    service.run()
