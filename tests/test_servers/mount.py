from server import service

from flask import Flask
from sanic import Sanic
from fastapi import FastAPI
import tornado

flask_app = Flask(__name__)
sanic_app = Sanic(__name__)
fastapi_app = FastAPI()


@flask_app.route("/hello")
def hello_world():
    return "<p>Hello, flask!</p>"


@sanic_app.get("/add")
def add(request):
    return "<p>Hello, sanic!</p>"


@fastapi_app.get("/items/{item_id}")
async def read_item(item_id):
    return {"item_id": item_id}


import starlette
service.set_backend(starlette)

service.mount(flask_app, '/flask')
service.mount(sanic_app, '/sanic')      # fixme
service.mount(fastapi_app, '/fastapi')

import django_settings
from django.http.response import HttpResponse
from django.urls import re_path


def django_test(request, route: str):
    print('ROUTE:', route)
    return HttpResponse(route)


django_settings.urlpatterns = [
    # path("admin/", admin.site.urls),
    re_path('test/(.*)', django_test),
]

service.mount(django_settings.wsgi, '/django_wsgi')
service.mount(django_settings.asgi, '/django_asgi')


# class MainHandler(tornado.web.RequestHandler):
#     def get(self):
#         self.write("Hello, tornado")
#
#
# def make_tornado_app():
#     return tornado.web.Application([
#         (r"/tornado", MainHandler),
#     ])
#
#
# service.mount(make_tornado_app(), '/tornado')


if __name__ == '__main__':
    service.run()
