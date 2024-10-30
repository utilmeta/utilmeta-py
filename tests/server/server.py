import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.dirname(__file__))
DB_PATH = os.path.join(os.path.dirname(__file__), 'db')
DB_OPS_PATH = os.path.join(os.path.dirname(__file__), 'db_ops')

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
    api='api.RootAPI',
    route='/api'
    # host='0.0.0.0' if env.PRODUCTION else '127.0.0.1',
    # port=80 if env.PRODUCTION else 8800,
)

from utilmeta.core.server.backends.django import DjangoSettings
from utilmeta.core.orm import DatabaseConnections, Database
from utilmeta.core.cache import CacheConnections, Cache
from utilmeta.ops.config import Operations

service.use(DjangoSettings(
    apps=['app']
))
service.use(Operations(
    route='ops',
    database=Database(
        name=DB_OPS_PATH,
        engine='sqlite3',
    )
))
service.use(DatabaseConnections({
    'default': Database(
        name=DB_PATH,
        engine='sqlite3',
        # user=env.DB_USER,
        # password=env.DB_PASSWORD,
        # port=env.DB_PORT
    )
}))
service.use(CacheConnections({
    'default': Cache(
        engine='locmem'
    )
}))

# ------ SET BACKEND
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
# --------

# if service.backend_name == 'sanic':
# sanic required to load app outside of the __main__ block
app = service.application()

if __name__ == '__main__':
    try:
        from pytest_cov.embed import cleanup_on_sigterm
    except ImportError:
        pass
    else:
        cleanup_on_sigterm()
    service.run()
