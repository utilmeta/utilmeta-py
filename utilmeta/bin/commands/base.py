import warnings
from typing import Optional

from ..base import BaseCommand, command
from utilmeta import UtilMeta
from utilmeta.utils import search_file, path_join, load_ini, read_from, import_obj
from ..constant import META_INI, BLUE, RED
import os
import sys


class BaseServiceCommand(BaseCommand):
    META_INI = META_INI
    script_name = "meta"

    def __init__(self, exe: str = None, *args: str, cwd: str = os.getcwd()):
        self.exe = exe  # absolute path of meta command tool
        self.sys_args = list(args)
        if exe:
            os.environ.setdefault("UTILMETA_EXECUTABLE_PATH", exe)

        if not os.path.isabs(cwd):
            cwd = path_join(os.getcwd(), cwd)

        self.cwd = cwd.replace("\\", "/")
        self.ini_path = self.get_ini_file(*args)

        self.base_path = os.path.dirname(self.ini_path) if self.ini_path else self.cwd
        os.environ.setdefault("UTILMETA_PROJECT_DIR", self.base_path)

        self.service_config = {}
        self._service = None
        self._application = None

        if self.ini_path:
            self.service_config = self.load_meta()

        if sys.path[0] != self.base_path:
            sys.path.insert(0, self.base_path)

        super().__init__(*self.sys_args, cwd=self.cwd)

    def get_ini_file(self, *args: str):
        project_dir = str(os.getenv("UTILMETA_PROJECT_DIR") or self.cwd)
        file = search_file("utilmeta.ini", path=project_dir) or search_file(
            META_INI, path=project_dir
        )
        if file:
            # if inside a project, use the found ini file
            return file
        # check
        ini_file = None
        exclude_params = []
        for i, arg in enumerate(args):
            if arg.startswith("--ini"):
                if "=" in arg:
                    ini_file = arg.split("=")[1]
                    exclude_params.append(i)
                else:
                    try:
                        ini_file = args[i + 1]
                        exclude_params.extend([i, i + 1])
                    except IndexError:
                        ini_file = None
                break
        if exclude_params:
            sys.argv = [self.exe] + [
                arg for i, arg in enumerate(sys.argv[1:]) if i not in exclude_params
            ]
            self.sys_args = [
                arg for i, arg in enumerate(args) if i not in exclude_params
            ]
        if ini_file:
            path = path_join(self.cwd, ini_file)
            if os.path.isdir(path):
                return search_file("utilmeta.ini", path=path) or search_file(
                    META_INI, path=path
                )
            return path
        return None

    def command_not_found(self):
        print(RED % f'{self.script_name or "meta"}: command not found: {self.arg_name}')
        if not self.ini_path:
            print(f"It probably due to your utilmeta project not initialized")
            print(
                f'please use {BLUE % "meta init"} in the project directory to initialize your project first'
            )
        exit(1)

    def load_meta(self) -> dict:
        config = load_ini(read_from(self.ini_path), parse_key=True)
        return config.get("utilmeta") or config.get("service") or {}

    @property
    def service_ref(self):
        return self.service_config.get("service")

    @property
    def main_file(self) -> Optional[str]:
        file: str = self.service_config.get("main")
        if not file:
            return None
        return os.path.join(
            self.service.project_dir, file if file.endswith(".py") else f"{file}.py"
        )

    @property
    def application_ref(self):
        return self.service_config.get("app")

    def load_application(self):
        if self.application_ref:
            self._application = import_obj(self.application_ref)
            try:
                from utilmeta import service
            except ImportError:
                raise RuntimeError(
                    "UtilMeta service not configured, "
                    "make sure you are inside a path with meta.ini, "
                    "and service is declared in meta.ini"
                )
            else:
                self._service = service
                return self._application

    def load_service(self):
        import utilmeta
        utilmeta._cmd_env = True

        if not self.service_ref:
            if self.application_ref:
                self.load_application()
            else:
                raise RuntimeError(
                    "UtilMeta service not configured, make sure you are inside a path with meta.ini"
                )

            if self._service:
                return self._service

        try:
            service = import_obj(self.service_ref)
        except Exception as e:
            warnings.warn(f'load service failed with error: {e}')
            if self.application_ref:
                print('trying to load application')
                self.load_application()
                if self._service:
                    return self._service
            raise
        if not isinstance(service, UtilMeta):
            raise RuntimeError(
                f"Invalid UtilMeta service: {self.service}, should be an UtilMeta instance"
            )
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
    @command("-h")
    def help(cls):
        """
        for helping
        """
        print(
            f"meta management tool usage:                                                          "
        )
        for key, doc in cls._documents.items():
            if not key:
                continue
            print(" ", BLUE % key, doc, "\n")
