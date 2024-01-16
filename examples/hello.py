from utilmeta import UtilMeta
from utilmeta.core import api
import flask


class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'


service = UtilMeta(
    __name__,
    name='demo',
    backend=flask,    # or flask / starlette / tornado / sanic
    api=RootAPI,
    route='/api'
)

app = service.application()  # wsgi app

if __name__ == '__main__':
    service.run()
