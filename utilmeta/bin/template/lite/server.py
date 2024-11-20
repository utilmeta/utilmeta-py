"""
This is a simple one-file project alternative when you setup UtilMeta project
"""
from utilmeta import UtilMeta
from utilmeta.core import api
import os
{import_backend}    # noqa

{plugins}  # noqa
class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'


production = bool(os.getenv('UTILMETA_PRODUCTION'))
service = UtilMeta(
    __name__,
    name='{name}',
    description='{description}',
    backend={backend},  # noqa
    production=production,
    version=(0, 1, 0),
    host='127.0.0.1',
    port=8000,
    origin='https://{host}' if production else None,
    route='/api',
    api=RootAPI
)
{operations} # noqa

app = service.application()     # used in wsgi/asgi server


if __name__ == '__main__':
    service.run()
    # try: http://127.0.0.1:8000/api/hello
