import inspect
import os.path

from .base import command, Arg
from .commands.setup import SetupCommand
from .commands.base import BaseServiceCommand
from utilmeta import __version__
from utilmeta.utils import run, import_obj
from .constant import BLUE, RED, YELLOW
import sys


class MetaCommand(BaseServiceCommand):
    # BACKENDS_PACKAGE = 'utilmeta.bin.backends'
    setup: SetupCommand

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_commands()

    def load_commands(self):
        try:
            self.load_service()
        except RuntimeError:
            return
        for name, cmd in self.service.commands.items():
            if not name:
                for cls in cmd:
                    self.merge(cls)
            else:
                self.mount(cmd, name=name)

    @classmethod
    @command('')
    def intro(cls):
        print(f'UtilMeta v{__version__} Management Command Line Tool')
        print('use meta -h for help')
        cls.help()

    @command('init')
    def init(self,
             app: str = Arg(alias='--app', default=None),
             service: str = Arg(alias='--service', default=None),
             main_file: str = Arg(alias='--main', default=None),
             ):
        """
        Initialize utilmeta project with a meta.ini file
        --app: specify the wsgi / asgi application
        --service: specify the reference of UtilMeta service
        --main: specify the reference of main file
        """
        if not self.ini_path:
            self.ini_path = os.path.join(self.cwd, self.META_INI)
            print(f'Initialize UtilMeta project with {self.ini_path}')
        else:
            config = self.service_config
            if config:
                print('UtilMeta project already initialized at {}'.format(self.ini_path))
                return
            print(f'Re-initialize UtilMeta project at {self.ini_path}')
        if not app:
            print(RED % 'meta init: you should use --app=<ref.to.your.app> '
                        'to specify your wsgi / asgi / python application reference')
            exit(1)
        # try to load
        try:
            app_obj = import_obj(app)
            if inspect.ismodule(app_obj):
                raise ValueError(f'--app should be a python application object, got module: {app_obj}')
        except Exception as e:
            print(RED % f'meta init: python application reference: {repr(app)} failed to load: {e}')
            exit(1)

        settings = dict(app=app)
        if service:
            settings['service'] = service
        if main_file:
            settings['main'] = main_file

        from utilmeta.utils import write_config
        write_config({
            'utilmeta': settings
        }, self.ini_path)

    def _get_openapi(self):
        from utilmeta.ops.config import Operations
        ops_config = self.service.get_config(Operations)
        if ops_config:
            return ops_config.openapi
        from utilmeta.core.api.specs.openapi import OpenAPI
        return OpenAPI(self.service)()

    @command()
    def gen_openapi(self, to: str = Arg(alias='--to', default='openapi.json')):
        """
        Generate OpenAPI document file for current service
        --to: target file name, default to be openapi.json
        """
        self.service.setup()  # setup here
        print(f'generate openapi document file for service: [{self.service.name}]')
        from utilmeta.core.api.specs.openapi import OpenAPI
        openapi = self._get_openapi()
        path = OpenAPI.save_to(openapi, to)
        print(f'OpenAPI document generated at {path}')

    @command()
    def gen_client(self,
                   openapi: str = Arg(alias='--openapi', default=None),
                   to: str = Arg(alias='--to', default='client.py'),
                   split_body_params: str = Arg(alias='--split-body-params', default=True),
                   black: str = Arg(alias='--black', default=True),
                   space_indent: str = Arg(alias='--spaces-indent', default=True),
                   ):
        """
        Generate UtilMeta Client code for current service or specified OpenAPI document (url or file)
        --openapi: specify target OpenAPI document (url / filepath / document string), default to be the document of current UtilMeta service
        --to: target file name, default to be openapi.json
        """
        from utilmeta.core.cli.specs.openapi import OpenAPIClientGenerator
        if openapi:
            print(f'generate client file based on openapi: {repr(openapi)}')
            generator = OpenAPIClientGenerator.generate_from(openapi)
        else:
            self.service.setup()  # setup here
            print(f'generate client file for service: [{self.service.name}]')
            openapi_docs = self._get_openapi()
            generator = OpenAPIClientGenerator(openapi_docs)
        generator.space_ident = space_indent
        generator.black_format = black
        generator.split_body_params = split_body_params
        path = generator(to)
        print(f'Client file generated at {path}')

    @command('-v', 'version')
    def version(self):
        """
        display the current UtilMeta version and service meta-info
        """
        import platform
        import sys
        from utilmeta.bin.constant import BLUE, GREEN, DOT
        print(f'     UtilMeta: v{ __version__}')
        try:
            _ = self.service
        except RuntimeError:
            # service not detect
            print(f'      service:', 'not detected')
        else:
            print(f'      service:', BLUE % self.service.name, f'({self.service.version_str})')
            print(f'        stage:', (BLUE % f'{DOT} production') if self.service.production else (GREEN % f'{DOT} debug'))
            print(f'      backend:', f'{self.service.backend_name} ({self.service.backend_version})',
                  f'| asynchronous' if self.service.asynchronous else '')
        print(f'  environment:', sys.version, platform.platform())

    @command
    def run(self,
            daemon: bool = Arg('-d', default=False),
            connect: bool = Arg('-c', default=False),
            log: str = Arg('--log', default='service.log'),
            ):
        """
        run utilmeta service and start to serve requests (for debug only)
        """
        if not self.main_file:
            print(RED % 'meta run: no main file specified in meta.ini')
            exit(1)
        print(f'UtilMeta service {BLUE % self.service.name} running at {self.main_file}')
        cmd = f'{sys.executable} {self.main_file}'
        if daemon:
            if os.name == 'posix':
                print(f'running service with nohup in background, writing log to {log}')
                cmd = f'nohup {cmd} > {log} 2>&1 &'
            else:
                print(YELLOW % 'ignoring daemon mode since only posix system support')
        if connect:
            from utilmeta.ops.cmd import try_to_connect
            try_to_connect()

        run(cmd)


def main():
    MetaCommand(*sys.argv)()


if __name__ == '__main__':
    main()
