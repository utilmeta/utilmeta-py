"""
This is a simple one-file project alternative when you setup UtilMeta project
"""
from utilmeta import UtilMeta
import django

service = UtilMeta(
    __name__,
    name='user-auth',
    backend=django,
    port=8003,
    route='/api',
    api='api.RootAPI'
)

from utilmeta.core.server.backends.django import DjangoSettings
from utilmeta.core.orm import DatabaseConnections, Database
from utilmeta.ops import Operations

service.use(DjangoSettings(
    secret_key='YOUR_SECRET_KEY',
    apps=['user']
))

service.use(DatabaseConnections({
    'default': Database(
        name='db',
        engine='sqlite3',
    )
}))
service.use(Operations(
    route='ops',
    database=Database(
        name='operations_db',
        engine='sqlite3',
    )
))

app = service.application()     # used in wsgi/asgi server

if __name__ == '__main__':
    service.run()
