from utilmeta import UtilMeta
from utilmeta.core.server.backends.django import DjangoSettings
from utilmeta.core.orm import DatabaseConnections, Database


def configure(service: UtilMeta):
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
