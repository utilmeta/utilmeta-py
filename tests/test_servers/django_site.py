import django
from django.urls import re_path
from django.http.response import HttpResponse
from utilmeta.core import api, response
import django_settings


class CalcAPI(api.API):
    class response(response.Response):
        result_key = 'data'
        message_key = 'msg'

    @api.get
    async def add(self, a: int, b: int) -> int:
        return a + b


def django_test(request, route: str):
    print('ROUTE:', route)
    return HttpResponse(route)


django_settings.urlpatterns = [
    # path("admin/", admin.site.urls),
    re_path('test/(.*)', django_test),
    CalcAPI.__as__(django, route='/calc', asynchronous=True),
    # CalcAPI.__as__(django, route='/calc2'),
]

if __name__ == "__main__":
    django_settings.main()
