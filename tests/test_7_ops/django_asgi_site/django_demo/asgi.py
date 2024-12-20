"""
ASGI config for django_demo project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
import sys

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_demo.settings")

application = get_asgi_application()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.dirname(__file__))

from utilmeta.ops import Operations
from utilmeta import UtilMeta
from utilmeta.core import api, response
from tests.conftest import get_operations_db

service = UtilMeta(
    __name__,
    name='django_demo_async',
    backend=application
)


@service.mount
@api.CORS(allow_origin='*')
class RootAPI(api.API):
    class PlusResponse(response.Response):
        result_key = 'data'
        message_key = 'error'

    response = PlusResponse

    @api.get
    async def sleep(self, a: float) -> PlusResponse[float]:
        import asyncio
        await asyncio.sleep(a)
        return self.PlusResponse(a)


PORT = 9100

Operations(
    route='ops',
    database=get_operations_db(),
    base_url=f'http://127.0.0.1:{PORT}',
    eager_migrate=True
).integrate(service)
