from django.urls import path, include
from django.contrib.auth.models import User
from rest_framework import routers, serializers, viewsets


# Serializers define the API representation.
class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ['url', 'username', 'email', 'is_staff']


# ViewSets define the view behavior.
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register(r'users', UserViewSet)

from ninja import NinjaAPI

ninja_api = NinjaAPI()


@ninja_api.get("/add")
def add(request, a: int, b: int):
    return {"result": a + b}


import django
from django.http.response import HttpResponse
from utilmeta.core import api, response


class TimeAPI(api.API):
    class response(response.Response):
        result_key = 'data'
        message_key = 'msg'

    @api.get
    def now(self):
        return self.request.time


def django_test(request, route: str):
    return HttpResponse(route)


from utilmeta import UtilMeta
from utilmeta.conf import Time

service = UtilMeta(
    __name__,
    name='time',
    backend=django,
    api=TimeAPI,
)
service.use(Time(
    datetime_format="%Y-%m-%d %H:%M:%S",
    use_tz=False
))


# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path('', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path("api-ninja/", ninja_api.urls),
    service.adapt('/api/v1/time')
]
