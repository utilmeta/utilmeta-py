import django
from utilmeta import UtilMeta

service = UtilMeta(__name__, backend=django, name='demo')

from utilmeta.core.server.backends.django import DjangoSettings
service.use(DjangoSettings())
service.setup()

from ninja import NinjaAPI
ninja_api = NinjaAPI()


@ninja_api.get("/add")
def add(request, a: int, b: int):
    return {"result": a + b}


service.mount(ninja_api, '/v1')

from utilmeta.core import api

@service.mount
class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'


app = service.application()


if __name__ == '__main__':
    service.run()
