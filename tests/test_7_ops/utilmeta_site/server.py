from utilmeta import UtilMeta
from utilmeta.core import api, response
import django


@api.CORS(allow_origin='*')
class RootAPI(api.API):
    class response(response.Response):
        result_key = 'data'
        message_key = 'msg'

    @api.get
    def add(self, a: int, b: int) -> int:
        return a + b

    @api.get
    def hello(self):
        return 'world'


PORT = 9090

service = UtilMeta(
    __name__,
    name='demo',
    backend=django,    # or flask / starlette / tornado / sanic
    port=PORT,
    api=RootAPI,
    route='/api'
)


from utilmeta.ops import Operations
service.use(Operations(
    route='ops',
    database=Operations.Database(
        name='operations_db',
        engine='sqlite3'  # or 'postgres' / 'mysql' / 'oracle'
    ),
    eager=True
    # base_url='http://127.0.0.1:{}/'.format(PORT),
))

app = service.application()  # wsgi app

if __name__ == '__main__':
    service.run()
