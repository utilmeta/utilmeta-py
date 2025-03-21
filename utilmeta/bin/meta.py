import inspect
import os.path

from .base import command, Arg
from .commands.setup import SetupCommand
from .commands.base import BaseServiceCommand
from utilmeta import __version__
from utilmeta.utils import run, import_obj, kill, Error
from .constant import BLUE, RED, YELLOW
import sys
import psutil


class MetaCommand(BaseServiceCommand):
    # BACKENDS_PACKAGE = 'utilmeta.bin.backends'
    setup: SetupCommand

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_commands()

    def command_not_found(self):
        if self.ini_path:
            # maybe figure out some non-invasion method in the future
            if self.arg_name in ["connect", "stats", "sync", "migrate_ops"]:
                print(
                    YELLOW
                    % f"meta {self.arg_name}: Operations config not integrated to application, "
                    "please follow the document at https://docs.utilmeta.com/py/en/guide/ops/"
                )
            elif self.arg_name in ["add", "makemigrations", "migrate"]:
                print(
                    YELLOW
                    % f"meta {self.arg_name}: DjangoSettings config not used in application"
                )
        super().command_not_found()

    def load_commands(self):
        try:
            self.load_service()
        except RuntimeError:
            return
        except Exception as e:
            from utilmeta.utils import Error
            err = Error(e)
            err.setup()
            print(err.message)
            print(RED % '[error]: load utilmeta service failed with error: {}'.format(e))
            return
        for name, cmd in self.service.commands.items():
            if not name:
                for cls in cmd:
                    self.merge(cls)
            else:
                self.mount(cmd, name=name)

    @classmethod
    @command("")
    def intro(cls):
        print(f"UtilMeta v{__version__} Management Command Line Tool")
        print("use meta -h for help")
        cls.help()

    @command("init")
    def init(
        self,
        name: str = Arg(default=None),
        app: str = Arg(alias="--app", default=None),
        service: str = Arg(alias="--service", default=None),
        main_file: str = Arg(alias="--main", default=None),
        pid_file: str = Arg(alias="--pid", default="service.pid"),
    ):
        """
        Initialize utilmeta project with a meta.ini file
        --app: specify the wsgi / asgi application
        --service: specify the reference of UtilMeta service
        --main: specify the reference of main file
        """
        if not self.ini_path:
            self.ini_path = os.path.join(self.cwd, self.META_INI)
            print(f"Initialize UtilMeta project with {self.ini_path}")
        else:
            config = self.service_config
            if config:
                print(
                    "UtilMeta project already initialized at {}".format(self.ini_path)
                )
                return
            print(f"Re-initialize UtilMeta project at {self.ini_path}")

        while True:
            if not app:
                print(
                    f"Please specify the reference of your WSGI / ASGI application, like package.to.your.app"
                )
                app = input(">>> ")
            # try to load
            try:
                app_obj = import_obj(app)
                if inspect.ismodule(app_obj):
                    raise ValueError(
                        f"--app should be a python application object, got module: {app_obj}"
                    )
                break
            except Exception as e:
                err = Error(e)
                err.setup()
                print(err.message)
                print(
                    RED
                    % f"python application reference: {repr(app)} failed to load: {e}"
                )
                app = None

        if not name:
            base_name = os.path.basename(os.path.dirname(self.ini_path))
            print(f"Please enter your project name (default: {base_name})")
            name = input(">>> ") or base_name

        settings = dict(app=app)
        if name:
            settings["name"] = name
        if main_file:
            settings["main"] = main_file
        if service:
            settings["service"] = service
        if pid_file:
            settings["pidfile"] = pid_file

        print(
            f"Initializing UtilMeta project [{BLUE % name}] with python application: {BLUE % app}"
        )

        from utilmeta.utils import write_config

        write_config({"utilmeta": settings}, self.ini_path)

    def _get_openapi(self):
        from utilmeta.ops.config import Operations

        ops_config = self.service.get_config(Operations)
        if ops_config:
            return ops_config.openapi
        from utilmeta.core.api.specs.openapi import OpenAPI

        return OpenAPI(self.service)()

    @command()
    def gen_openapi(self, to: str = Arg(alias="--to", default="openapi.json")):
        """
        Generate OpenAPI document file for current service
        --to: target file name, default to be openapi.json
        """
        self.service.setup()  # setup here
        print(f"generate openapi document file for service: [{self.service.name}]")
        from utilmeta.core.api.specs.openapi import OpenAPI

        openapi = self._get_openapi()
        path = OpenAPI.save_to(openapi, to)
        print(f"OpenAPI document generated at {path}")

    @command()
    def gen_client(
        self,
        openapi: str = Arg(alias="--openapi", default=None),
        to: str = Arg(alias="--to", default="client.py"),
        split_body_params: str = Arg(alias="--split-body-params", default=True),
        black: str = Arg(alias="--black", default=True),
        space_indent: str = Arg(alias="--spaces-indent", default=True),
    ):
        """
        Generate UtilMeta Client code for current service or specified OpenAPI document (url or file)
        --openapi: specify target OpenAPI document (url / filepath / document string), default to be the document of current UtilMeta service
        --to: target file name, default to be openapi.json
        """
        from utilmeta.core.cli.specs.openapi import OpenAPIClientGenerator

        if openapi:
            print(f"generate client file based on openapi: {repr(openapi)}")
            generator = OpenAPIClientGenerator.generate_from(openapi)
        else:
            self.service.setup()  # setup here
            print(f"generate client file for service: [{self.service.name}]")
            openapi_docs = self._get_openapi()
            generator = OpenAPIClientGenerator(openapi_docs)
        generator.space_ident = space_indent
        generator.black_format = black
        generator.split_body_params = split_body_params
        path = generator(to)
        print(f"Client file generated at {path}")

    @command("-v", "version")
    def version(self):
        """
        display the current UtilMeta version and service meta-info
        """
        import platform
        import sys
        from utilmeta.bin.constant import BLUE, GREEN, DOT

        print(f"     UtilMeta: v{ __version__}")
        try:
            _ = self.service
        except RuntimeError:
            # service not detect
            print(f"      service:", "not detected")
        else:
            print(
                f"      service:",
                BLUE % self.service.name,
                f"({self.service.version_str})",
            )
            print(
                f"        stage:",
                (BLUE % f"{DOT} production")
                if self.service.production
                else (GREEN % f"{DOT} debug"),
            )
            print(
                f"      backend:",
                f"{self.service.backend_name} ({self.service.backend_version})",
                f"| asynchronous" if self.service.asynchronous else "",
            )
        print(f"  environment:", sys.version, platform.platform())

    @command
    def check(self):
        """
        check if utilmeta service has no errors and ready to run
        """
        if not self._service:
            print(RED % f'meta check failed: service not loaded')
            return
        try:
            _ = self.service.application()
        except Exception as e:
            from utilmeta.utils import Error
            err = Error(e)
            err.setup()
            print(err.message)
            print(RED % f'[error]: load utilmeta application: {repr(self.service.name)} failed with error: {e}')
            print(RED % f'meta check failed: application not loaded')
            return
        print(f'meta check passed for service: {BLUE % self.service.name}')

    @command
    def run(
        self,
        daemon: bool = Arg("-d", default=False),
        connect: bool = Arg("-c", default=False),
        log: str = Arg("--log", default="service.log"),
    ):
        """
        run utilmeta service and start to serve requests (for debug only)
        """
        if not self.main_file:
            print(RED % "meta run: no main file specified in meta.ini")
            exit(1)
        print(
            f"UtilMeta service {BLUE % self.service.name} running at {self.main_file}"
        )
        if os.name == "nt":
            env = f"set PYTHONPATH=%PYTHONPATH%;{self.service.project_dir} &&"
        else:
            env = f"PYTHONPATH=$PYTHONPATH:{self.service.project_dir}"
        cmd = f"{sys.executable} {self.main_file}"
        if daemon:
            if os.name == "posix":
                print(f"running service with nohup in background, writing log to {log}")
                cmd = f"{env} nohup {cmd} > {log} 2>&1 &"
            else:
                print(YELLOW % "ignoring daemon mode since only posix system support")
        if connect:
            from utilmeta.ops.cmd import try_to_connect

            try_to_connect()

        run(f"{env} {cmd}")

    @command
    def down(self):
        pid = self.service.pid
        if not pid:
            if self.service.pid_file:
                print(
                    RED
                    % f"meta down: PID not found in pidfile, service may not started yet"
                )
            else:
                print(
                    RED % f"meta down: requires pidfile set in meta.ini, no pid found"
                )
            exit(1)
        try:
            proc = psutil.Process(pid)
        except psutil.NoSuchProcess:
            print(
                f"meta down: service [{self.service.name}](pid={pid}) already stopped"
            )
            return
        except psutil.Error as e:
            print(RED % f"meta down: load process: {pid} failed with error: {e}")
            exit(1)
        proc.kill()
        print(f"meta down: service [{self.service.name}](pid={pid}) stopped")

    @command
    def restart(
        self,
        connect: bool = Arg("-c", default=False),
        log: str = Arg("--log", default="service.log"),
    ):
        pid = self.service.pid
        if not pid:
            if self.service.pid_file:
                return self.run(daemon=True, connect=connect, log=log)
            print(RED % f"meta restart: requires pidfile set in meta.ini, no pid found")
            exit(1)
        try:
            proc = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return self.run(daemon=True, connect=connect, log=log)
        except psutil.Error as e:
            print(RED % f"meta restart: load process: {pid} failed with error: {e}")
            exit(1)
        proc.kill()
        print(f"current service [{self.service.name}](pid={pid}) stopped")
        return self.run(daemon=True, connect=connect, log=log)


def main():
    MetaCommand(*sys.argv)()


if __name__ == "__main__":
    main()
