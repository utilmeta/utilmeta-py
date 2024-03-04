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
    production=env.PRODUCTION,
    version=(0, 1, 0),
    host='0.0.0.0' if env.PRODUCTION else '127.0.0.1',
    port=80 if env.PRODUCTION else 8800,
    background='-b' in sys.argv,
    asynchronous=True
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


class RootAPI(api.API):
    class response(response.Response):
        result_key = 'data'
        message_key = 'error'

    @api.get
    def hello(self):
        return 'world'


service.mount(RootAPI, route='/api')
# app = service.application()


if __name__ == '__main__':
    import starlette
    service.set_backend(starlette)
    service.run()
