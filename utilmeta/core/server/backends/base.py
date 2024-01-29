from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from utilmeta import UtilMeta
    from utilmeta.core.api import API
from utilmeta.utils import BaseAdaptor, exceptions
import re
import inspect


class ServerAdaptor(BaseAdaptor):
    # __backends_route__ = 'backends'

    @classmethod
    def reconstruct(cls, adaptor: 'BaseAdaptor'):
        pass

    def adapt(self, api: 'API', route: str, asynchronous: bool = None):
        raise NotImplementedError

    @classmethod
    def get_module_name(cls, obj: 'UtilMeta'):
        if inspect.ismodule(obj):
            # maybe the backend
            return obj.__name__
        return super().get_module_name(obj.backend)

    @classmethod
    def qualify(cls, obj: 'UtilMeta'):
        if not cls.backend or not obj.backend:
            return False
        return cls.get_module_name(obj.backend).lower() == cls.get_module_name(cls.backend).lower()

    backend = None
    default_asynchronous = False
    application_cls = None
    request_adaptor_cls = None
    response_adaptor_cls = None
    sync_db_adaptor_cls = None
    async_db_adaptor_cls = None
    DEFAULT_PORT = 8000

    def __init__(self, config: 'UtilMeta'):
        self.root = None
        self.config = config
        self.background = config.background
        self.asynchronous = config.asynchronous
        if self.asynchronous is None:
            config.asynchronous = self.asynchronous = self.default_asynchronous
        self.proxy = None

    @property
    def root_pattern(self):
        if not self.config.root_url:
            return None
        return re.compile('%s/(.*)' % self.config.root_url.strip('/'))

    def load_route(self, path: str):
        if not self.config.root_url:
            return path
        path = path.strip('/')
        match = self.root_pattern.match(path)
        if match:
            return match.groups()[0]
        if path == self.config.root_url:
            return ''
        raise exceptions.NotFound

    def resolve(self):
        if self.root:
            return self.root
        self.root = self.config.resolve()
        return self.root

    def setup(self):
        raise NotImplementedError

    def run(self, **kwargs):
        raise NotImplementedError

    def mount(self, app, route: str):
        raise NotImplementedError

    def application(self):
        pass

    @classmethod
    def is_asgi(cls, app):
        if not inspect.isfunction(app):
            app = getattr(app, '__call__', None)
        if not app:
            return False
        return inspect.iscoroutinefunction(app)
