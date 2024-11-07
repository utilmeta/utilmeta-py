from ..base import BaseCommand, command
from utilmeta import UtilMeta
from utilmeta.utils import search_file, path_join, load_ini, read_from, import_obj
from ..constant import META_INI, BLUE, RED
import os
import sys


class BaseServiceCommand(BaseCommand):
    META_INI = META_INI
    script_name = 'meta'

    def __init__(self, exe: str = None, *args: str, cwd: str = os.getcwd()):
        self.exe = exe      # absolute path of meta command tool
        self.sys_args = list(args)
        if exe:
            os.environ.setdefault('META_ABSOLUTE_PATH', exe)

        if not os.path.isabs(cwd):
            cwd = path_join(os.getcwd(), cwd)

        self.cwd = cwd.replace('\\', '/')
        self.ini_path = search_file('utilmeta.ini', path=cwd) or search_file(META_INI, path=cwd)
        self.base_path = os.path.dirname(self.ini_path) if self.ini_path else self.cwd
        self.service_config = {}
        self._service = None
        self._application = None

        if self.ini_path:
            self.service_config = self.load_meta()

        if sys.path[0] != self.base_path:
            sys.path.insert(0, self.base_path)

        super().__init__(*self.sys_args, cwd=self.cwd)

    def command_not_found(self):
        print(RED % F'{self.script_name or "meta"}: command not found: {self.arg_name}')
        if not self.ini_path:
            print(f'It probably due to your utilmeta project not initialized')
            print(f'please use {BLUE % "meta init"} in the project directory to initialize your project first')
        exit(1)

    def load_meta(self) -> dict:
        config = load_ini(read_from(self.ini_path), parse_key=True)
        return config.get('utilmeta') or config.get('service') or {}

    @property
    def service_ref(self):
        return self.service_config.get('service')

    @property
    def main_file(self):
        file: str = self.service_config.get('main')
        if not file:
            return file
        if file.endswith('.py'):
            return file
        return file + '.py'

    @property
    def application_ref(self):
        return self.service_config.get('app')

    def load_service(self):
        import utilmeta
        utilmeta._cmd_env = True

        if not self.service_ref:
            if self.application_ref:
                self._application = import_obj(self.application_ref)
                try:
                    from utilmeta import service
                except ImportError:
                    raise RuntimeError('UtilMeta service not configured, '
                                       'make sure you are inside a path with meta.ini, '
                                       'and service is declared in meta.ini')
                else:
                    self._service = service
                    return service
            else:
                raise RuntimeError('UtilMeta service not configured, make sure you are inside a path with meta.ini')

        service = import_obj(self.service_ref)
        if not isinstance(service, UtilMeta):
            raise RuntimeError(f'Invalid UtilMeta service: {self.service}, should be an UtilMeta instance')
        self._service = service
        return service

    @property
    def service(self) -> UtilMeta:
        if self._service:
            return self._service
        return self.load_service()

    # def check_service(self):
    #     if not self.service_ref:
    #         raise RuntimeError('UtilMeta service not configured, make sure you are inside a path with meta.ini')

    @classmethod
    @command('-h')
    def help(cls):
        """
        for helping
        """
        print(f'meta management tool usage:                                                          ')
        for key, doc in cls._documents.items():
            if not key:
                continue
            print(' ', BLUE % key, doc, '\n')
