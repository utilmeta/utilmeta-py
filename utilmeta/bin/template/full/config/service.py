from utilmeta import UtilMeta
from config.conf import configure
from config.env import env

{import_backend}  # noqa

service = UtilMeta(
    __name__,
    name="{name}",
    description="{description}",
    backend={backend},  # noqa
    production=env.PRODUCTION,
    version=(0, 1, 0),
    host="127.0.0.1",
    port=8000,
    origin="https://{host}" if env.PRODUCTION else None,
    api="service.api.RootAPI",
    route="/api",
)
configure(service)
