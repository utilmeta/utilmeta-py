from typing import Union, Callable, Type, TypeVar, Optional
import sys
import os
from utilmeta.utils import import_obj, awaitable, search_file
from utilmeta.conf.base import Config
import inspect
from utilmeta.core.api import API

# if TYPE_CHECKING:
#     from utilmeta.core.api.specs.base import BaseAPISpec

T = TypeVar('T')


class UtilMeta:
    # DEFAULT_API_SPEC = 'utilmeta.core.api.specs.openapi.OpenAPI'

    def __init__(
        self,
        module_name: Optional[str], *,
        backend,
        name: str = None,
        title: str = None,
        description: str = None,
        production: bool = None,
        host: str = None,
        port: int = None,
        scheme: str = 'http',
        version: tuple = None,
        application=None,
        info: dict = None,
        # for document generation
        background: bool = False,
        asynchronous: bool = None,
        auto_reload: bool = None,
        api=None,
        route: str = '',
    ):
        """
            ! THERE MUST BE NO IMPORT BEFORE THE CONFIG IS ASSIGNED PROPERLY !
            if there is, the utils will use the incorrect initial settings Config and cause the
            runtime error (hard to find)
        """

        # if not name.replace('-', '_').isidentifier():
        #     raise ValueError(f'{self.__class__}: service name ({repr(name)}) should be a valid identifier')

        self.module = sys.modules.get(module_name or '__main__')

        # 1. find meta.ini
        # 2. os.path.dirname(self.module.__file__)
        # 3. sys.path[0] / os.getcwd()
        self.meta_path = search_file('meta.ini')
        self.project_dir = os.path.dirname(self.meta_path) if self.meta_path else os.getcwd()

        self.root_api = api
        self.root_url = str(route or '').strip('/')
        # self.root_url = str(root_url).strip('/')
        self.production = production
        self.version = version
        # self.config = config
        self.background = background
        self.asynchronous = asynchronous

        self.name = name or module_name
        self.title = title
        self.description = description
        self.module_name = module_name
        self.host = host
        self.port = port
        self.scheme = scheme
        self.auto_reload = auto_reload
        self.info = info
        self.configs = {}
        self.commands = {}
        self.events = {}
        self.document = None
        # generated API document will be here

        self._application = application
        self._ready = False

        import utilmeta
        try:
            srv: 'UtilMeta' = utilmeta.service
        except AttributeError:
            utilmeta.service = self
        else:
            if srv.name != self.name:
                raise ValueError(f'Conflict service: {repr(self.name)}, {srv.name} in same process')
            utilmeta.service = self

        self.backend = None
        self.backend_name = None
        from utilmeta.core.server.backends.base import ServerAdaptor
        self.adaptor: Optional[ServerAdaptor] = None
        self.set_backend(backend)

        self.routes = {}

    def set_backend(self, backend):
        if not backend:
            return

        from utilmeta.core.server.backends.base import ServerAdaptor

        application = None
        # backend_name = None

        if isinstance(backend, str):
            backend_name = backend
        elif isinstance(backend, type) and issubclass(backend, ServerAdaptor):
            self.adaptor = backend(self)
            backend = backend.backend
            backend_name = getattr(backend, '__name__', str(backend))
        elif inspect.ismodule(backend):
            backend_name = getattr(backend, '__name__', str(backend))
        else:
            # maybe an application
            module = getattr(backend, '__module__', None)
            if module and callable(backend):
                # application
                application = backend
                backend_name = str(module).split('.')[0]
                backend = import_obj(backend_name)
            else:
                raise TypeError(f'Invalid service backend: {repr(backend)}, '
                                f'must be a supported module or application')

        self.backend = backend
        self.backend_name = backend_name

        if application:
            self._application = application

        if not self.adaptor:
            self.adaptor = ServerAdaptor.dispatch(self)

        if self._application and self.adaptor.application_cls:
            if not isinstance(self._application, self.adaptor.application_cls):
                raise ValueError(f'Invalid application for {repr(self.backend_name)}: {application}')

    def __repr__(self):
        return f'UtilMeta({repr(self.module_name)}, ' \
               f'name={repr(self.name)}, ' \
               f'backend={self.backend}, ' \
               f'version={self.version}, background={self.background})'

    def __str__(self):
        return self.__repr__()

    def register_command(self, command_cls, name: str = None):
        from utilmeta.bin.base import BaseCommand
        if not issubclass(command_cls, BaseCommand):
            raise TypeError(f'UtilMeta: Invalid command class: {command_cls} to register, '
                            f'must be subclass of BaseCommand')
        if name:
            if name in self.commands:
                if self.commands[name] != command_cls:
                    raise ValueError(f'UtilMeta: conflict command'
                                     f' [{repr(name)}]: {command_cls}, {self.commands[name]}')
                return
            self.commands[name] = command_cls
        else:
            self.commands.setdefault(None, []).append(command_cls)

    def use(self, config):
        if isinstance(config, Config):
            config.hook(self)
        if isinstance(config, type):
            self.configs[config] = config()
        elif isinstance(config, object):
            self.configs[config.__class__] = config

    def get_config(self, config_class: Type[T]) -> Optional[T]:
        obj = self.configs.get(config_class)
        if obj:
            return obj
        for cls, config in self.configs.items():
            if issubclass(cls, config_class):
                return config
        return None

    def setup(self):
        if self._ready:
            return
        for cls, config in self.configs.items():
            if isinstance(config, Config):
                config.setup(self)
        self._ready = True

    def startup(self):
        for cls, config in self.configs.items():
            if isinstance(config, Config):
                config.on_startup(self)
        for func in self.events.get('startup', []):
            func()

    @awaitable(startup)
    async def startup(self):
        for cls, config in self.configs.items():
            if isinstance(config, Config):
                r = config.on_startup(self)
                if inspect.isawaitable(r):
                    await r
        for func in self.events.get('startup', []):
            r = func()
            if inspect.isawaitable(r):
                await r

    def shutdown(self):
        for cls, config in self.configs.items():
            if isinstance(config, Config):
                config.on_startup(self)
        for func in self.events.get('shutdown', []):
            func()

    @awaitable(shutdown)
    async def shutdown(self):
        for cls, config in self.configs.items():
            if isinstance(config, Config):
                r = config.on_shutdown(self)
                if inspect.isawaitable(r):
                    await r
        for func in self.events.get('shutdown', []):
            r = func()
            if inspect.isawaitable(r):
                await r

    def on_startup(self, f):
        if callable(f):
            self.events.setdefault('startup', []).append(f)

    def on_shutdown(self, f):
        if callable(f):
            self.events.setdefault('shutdown', []).append(f)

    def mount(self, api: Union[str, Callable, Type[API]] = None, route: str = ''):
        if not api:
            def deco(_api):
                return self.mount(_api, route=route)
            return deco
        elif isinstance(api, str):
            pass
        elif inspect.isclass(api) and issubclass(api, API):
            pass
        else:
            # try to mount a wsgi/asgi app
            if not route:
                raise ValueError('Mounting applications required not-empty route')
            if not self.adaptor:
                raise ValueError('UtilMeta: backend is required to mount applications')
            self.adaptor.mount(api, route=route)
            return

        if self.root_api:
            if self.root_api != api:
                raise ValueError(f'UtilMeta: root api conflicted: {api}, {self.root_api}, '
                                 f'you can only mount a service once')
            return
        self.root_api = api
        self.root_url = str(route).strip('/')

    # def mount_ws(self, ws: Union[str, Callable], route: str = ''):
    #     pass

    def resolve(self):
        if callable(self.root_api):
            return self.root_api
        if isinstance(self.root_api, str):
            if '.' not in self.root_api:
                # in current module
                root_api = getattr(self.module, self.root_api)
            else:
                root_api = import_obj(self.root_api)
            self.root_api = root_api
        if not callable(self.root_api):
            raise ValueError(f'utilMeta: api not mount')
        return self.root_api

    def run(self, **kwargs):
        if not self.adaptor:
            raise NotImplementedError('UtilMeta: service backend not specified')
        self.setup()
        return self.adaptor.run(**kwargs)

    def application(self):
        if not self.adaptor:
            raise NotImplementedError('UtilMeta: service backend not specified')
        self.setup()
        app = self.adaptor.application()
        self._application = app
        return app

    @property
    def origin(self):
        host = self.host or '127.0.0.1'
        port = self.port
        if port == 80 and self.scheme == 'http':
            port = None
        elif port == 443 and self.scheme == 'https':
            port = None
        if port:
            host += f':{port}'
        return f'{self.scheme or "http"}://{host}'

    @property
    def base_url(self):
        if self.root_url:
            return self.origin + '/' + self.root_url
        return self.origin

    # def generate(self, spec: Union[str, Type['BaseAPISpec']] = DEFAULT_API_SPEC):
    #     if self.document:
    #         return self.document
