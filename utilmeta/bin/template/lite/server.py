"""
This is a simple one-file project alternative when you setup UtilMeta project
"""
from utilmeta import UtilMeta
from utilmeta.core import api
from env import env
import sys
import {backend}


service = UtilMeta(
    __name__,
    name='{name}',
    description='{description}',
    backend={backend},
    production=env.PRODUCTION,
    version=(0, 1, 0),
    host='{host}' if env.PRODUCTION else '127.0.0.1',
    port=80 if env.PRODUCTION else 8000,
    background='-b' in sys.argv,
)


class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'


service.mount(RootAPI, route='/api')

app = service.application()     # used in wsgi/asgi server


if __name__ == '__main__':
    service.run()
    # try: http://127.0.0.1:8000/api/hello
