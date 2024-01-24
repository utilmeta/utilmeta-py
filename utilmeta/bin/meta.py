from .base import command
from .commands.setup import SetupCommand
from .commands.base import BaseServiceCommand
from utilmeta import __version__
from utilmeta.utils import run
from .constant import BLUE
import sys


class MetaCommand(BaseServiceCommand):
    # BACKENDS_PACKAGE = 'utilmeta.bin.backends'
    setup: SetupCommand

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_commands()

    def load_commands(self):
        if not self.service_ref:
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
            self.check_service()
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
    def run(self):
        """
        run the api server and start to serve requests (for debug only)
        """
        print(f'UtilMeta service {BLUE % self.service.name} running at {self.main_file}')
        run(f'python {self.main_file}')


def main():
    MetaCommand(*sys.argv)()


if __name__ == '__main__':
    main()
