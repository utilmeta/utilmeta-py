from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from utilmeta import UtilMeta
    from utilmeta.core.api import API
from utilmeta.utils import BaseAdaptor, exceptions
import re


class ServerAdaptor(BaseAdaptor):
    # __backends_route__ = 'backends'

    @classmethod
    def reconstruct(cls, adaptor: 'BaseAdaptor'):
        pass

    @classmethod
    def adapt(cls, api: 'API', route: str, asynchronous: bool = None):
        raise NotImplementedError

    @classmethod
    def get_module_name(cls, obj: 'UtilMeta'):
        return super().get_module_name(obj.backend)

    @classmethod
    def qualify(cls, obj: 'UtilMeta'):
        if not cls.backend:
            return False
        if isinstance(obj.backend, str):
            return cls.backend.__name__.lower() == obj.backend.lower()
        return cls.backend == obj.backend

    backend = None
    default_asynchronous = False
    application_cls = None
    request_adaptor_cls = None
    response_adaptor_cls = None
    sync_db_adaptor_cls = None
    async_db_adaptor_cls = None

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

    def application(self):
        pass

    # def resolve_proxy(self, request):
    #     from utilmeta.core.request import Request
    #     from utilmeta.core.response import Response
    #     if not isinstance(request, Request):
    #         request = Request(request)
    #     if not self.proxy:
    #         return None
    #     invoke = self.proxy.get(request.current_route) or request.reroute_target
    #     # get invoke template for proxy service or mismatched version reroute
    #     if invoke:
    #         # proxy request
    #         return Response()(invoke.__proxy__(request))
    #     return None
