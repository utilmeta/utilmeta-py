"""
This is a simple one-file project alternative when you setup UtilMeta project
"""
from utilmeta import UtilMeta
from utilmeta.core import api
import django

service = UtilMeta(
    __name__,
    name='user-auth',
    backend=django,
    port=8003,
)

from utilmeta.core.server.backends.django import DjangoSettings
from utilmeta.core.orm import DatabaseConnections, Database

service.use(DjangoSettings(
    secret_key='YOUR_SECRET_KEY',
    apps=['auth']
))

service.use(DatabaseConnections({
    'default': Database(
        name='user',
        engine='sqlite3',
    )
}))

from user.api import UserAPI


class RootAPI(api.API):
    user: UserAPI  # new


service.mount(RootAPI, route='/api')
app = service.application()     # used in wsgi/asgi server

if __name__ == '__main__':
    service.run()
