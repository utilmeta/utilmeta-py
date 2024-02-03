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
    apps=['app', 'rest_framework', 'django.contrib.auth'],
    root_urlconf='django_urls',
    append_slash=True,
    extra=dict(
        REST_FRAMEWORK={
            'DEFAULT_RENDERER_CLASSES': [
                'rest_framework.renderers.JSONRenderer',
            ]
        }
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
service.setup()

from utilmeta.core import api, response
from ninja import NinjaAPI
from app.models import User
from rest_framework import routers, serializers, viewsets


# Serializers define the API representation.
class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'signup_time', 'admin']


# ViewSets define the view behavior.
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register(r'users', UserViewSet)

ninja_api = NinjaAPI()

@ninja_api.get("/hello")
def hello(request, name):
    return f"Hello {name}"


class RootAPI(api.API):
    class response(response.Response):
        result_key = 'data'
        message_key = 'error'

    @api.get
    def hello(self):
        return 'world'


service.mount(RootAPI, route='/api')
service.mount(router, route='/drf')
service.mount(ninja_api, route='/ninja')

app = service.application()

if __name__ == '__main__':
    service.run()
