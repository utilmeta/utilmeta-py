from utilmeta import UtilMeta
from utilmeta.core import api
import django


class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'


service = UtilMeta(
    __name__,
    name='demo',
    backend=django,    # or flask / starlette / tornado / sanic
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
    base_url='https://blog.mysite.com/api',
))

app = service.application()  # wsgi app

if __name__ == '__main__':
    service.run()
