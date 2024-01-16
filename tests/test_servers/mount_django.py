from utilmeta import UtilMeta
import django

service = UtilMeta(
    __name__,
    name='blog',
    description='Blog - test service for utilmeta',
    backend=django
)


from utilmeta.core.server.backends.django import DjangoSettings
from utilmeta.core.orm import DatabaseConnections, Database
service.use(DjangoSettings(
    apps=['app'],
    root_urlconf='django_urls'
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
app = service.application()

if __name__ == '__main__':
    service.run()
