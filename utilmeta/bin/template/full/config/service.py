from utilmeta import UtilMeta
from config.conf import configure
from config.env import env
{import_backend}    # noqa

service = UtilMeta(
    __name__,
    name='{name}',
    description='{description}',
    backend={backend},  # noqa
    production=env.PRODUCTION,
    version=(0, 1, 0),
    host='{host}' if env.PRODUCTION else '127.0.0.1',
    port=80 if env.PRODUCTION else 8000,
)
service.mount('service.api.RootAPI', route='/api')
configure(service)
