from utilmeta import UtilMeta
from utilmeta.core.server.backends.django import DjangoSettings
from utilmeta.core.orm import DatabaseConnections, Database
from utilmeta.ops import Operations


def configure(service: UtilMeta):
    service.use(Operations(
        route='ops',
        database=Database(
            name='blog_ops'
        ),
    ))
    service.use(DjangoSettings(
        apps=['blog'],
        secret_key='YOUR_SECRET_KEY'
    ))
    service.use(DatabaseConnections({
        'default': Database(
            name='db',
            engine='sqlite3',
        )
    }))
    service.setup()
