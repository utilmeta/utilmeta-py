from utilmeta import UtilMeta
from config.conf import configure
from config.env import env
import {backend}
import sys

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
service.mount('service.api.RootAPI', route='/api')
configure(service)
