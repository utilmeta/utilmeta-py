import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.dirname(__file__))

from utilmeta import UtilMeta
from utilmeta.conf import Env
# import starlette
# import fastapi
# import django
# import sanic
import sys


class ServiceEnvironment(Env):
    PRODUCTION: bool = False
    SECRET_KEY: str = ''
    # DB_USER: str
    # DB_PASSWORD: str


env = ServiceEnvironment(sys_env='BLOG_')

__all__ = ['service']

service = UtilMeta(
    __name__,
    name='blog',
    description='Blog - test service for utilmeta',
    backend=None,
    asynchronous=None,
    production=env.PRODUCTION,
    version=(0, 1, 0),
    # host='0.0.0.0' if env.PRODUCTION else '127.0.0.1',
    # port=80 if env.PRODUCTION else 8800,
)

from utilmeta.core.server.backends.django import DjangoSettings
from utilmeta.core.orm import DatabaseConnections, Database
from utilmeta.ops.config import Operations

service.use(DjangoSettings(
    apps=['app']
))
service.use(Operations(
    route='ops',
    database=Database(
        name='db_ops',
        engine='sqlite3',
    )
))
service.use(DatabaseConnections({
    'default': Database(
        name='db',
        engine='sqlite3',
        # user=env.DB_USER,
        # password=env.DB_PASSWORD,
        # port=env.DB_PORT
    )
}))

from utilmeta.core import api, response
from api import TestAPI


def shutdown():
    import psutil
    proc = psutil.Process(os.getpid())
    proc.terminate()


class RootAPI(api.API):
    test: TestAPI

    class response(response.Response):
        result_key = 'data'
        message_key = 'error'

    @api.get
    def hello(self):
        return self.request.path

    @api.get
    def shutdown(self):
        import threading
        threading.Thread(target=shutdown).start()


service.mount(RootAPI, route='/api')
# app = service.application()

backend = None
port = None
asynchronous = None
for arg in sys.argv:
    if arg.startswith('--backend='):
        backend = __import__(arg.split('--backend=')[1])
    if arg.startswith('--port='):
        port = int(arg.split('--port=')[1])
    if arg == '--async':
        asynchronous = True
    if arg == '--sync':
        asynchronous = False
if backend:
    service.set_backend(backend)
else:
    import django
    service.set_backend(django)
if port:
    service.port = port
if asynchronous is not None:
    service.set_asynchronous(asynchronous)

app = service.application()

if __name__ == '__main__':
    try:
        from pytest_cov.embed import cleanup_on_sigterm
    except ImportError:
        pass
    else:
        cleanup_on_sigterm()
    service.run()
