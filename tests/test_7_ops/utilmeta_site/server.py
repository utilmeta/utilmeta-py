import os
import sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.dirname(__file__))

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
from tests.conftest import get_operations_db
service.use(Operations(
    route='ops',
    database=get_operations_db(),
    eager_migrate=True
    # base_url='http://127.0.0.1:{}/'.format(PORT),
))

app = service.application()  # wsgi app

if __name__ == '__main__':
    try:
        from pytest_cov.embed import cleanup_on_sigterm
    except ImportError:
        pass
    else:
        cleanup_on_sigterm()
    service.run()
