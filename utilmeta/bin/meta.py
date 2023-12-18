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
        cls.version(with_help=True)
        cls.help()

    @classmethod
    @command('-v', 'version')
    def version(cls, with_help=False):
        """
        display the current UtilMeta version
        """
        print(f'UtilMeta v{__version__} Management Command Line Tool')
        if with_help:
            print('use meta -h for help')

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
