import sys
import os
import time
import subprocess
import signal

import django
import pytest
import psutil
from utilmeta import UtilMeta
from typing import Union
from pathlib import Path
from utilmeta.utils import ignore_errors
# from django import VERSION as DJANGO_VERSION
TEST_PATH = os.path.dirname(__file__)
SERVICE_PATH = os.path.join(TEST_PATH, 'server')
PARAMETRIZE_CONFIG = False
CONNECT_TIMEOUT = 15
CONNECT_INTERVAL = 0.2
WINDOWS = os.name == 'nt'

# if WINDOWS:
#     try:
#         from pytest_cov.embed import cleanup_on_signal
#     except ImportError:
#         pass
#     else:
#         cleanup_on_signal(signal.SIGBREAK)
#
#         import signal
#
#         def shutdown(frame, signum):
#             exit(0)
#         signal.signal(signal.SIGBREAK, shutdown)
# else:
#     try:
#         from pytest_cov.embed import cleanup_on_sigterm
#         # Clean up coverage data before each test run
#     except ImportError:
#         pass
#     else:
#         cleanup_on_sigterm()


@pytest.fixture(params=('default', 'mysql', 'postgresql'), scope="module")
def db_using(request):
    return request.param


def get_operations_db(engine: str = None):
    engine = engine or os.environ.get('UTILMETA_OPERATIONS_DATABASE_ENGINE') or 'sqlite3'
    from utilmeta.core.orm import Database
    if engine == 'mysql':
        return Database(
            engine=engine,
            name='utilmeta_test_ops_db',
            host='127.0.0.1',
            port=3306,
            user='test_user',
            password='test-tmp-password',
        )
    elif engine == 'postgresql':
        return Database(
            engine=engine,
            name='utilmeta_test_ops_db',
            host='127.0.0.1',
            port=5432,
            user='test_user',
            password='test-tmp-password',
        )
    return Database(engine='sqlite3', name='operations_db')


# def patch_time():
#     if os.environ.get('UTILMETA_OPERATIONS_DATABASE_ENGINE') == 'postgresql' and django.VERSION <= (3, 2):
#         try:
#             from utilmeta import service
#         except ImportError:
#             pass
#         else:
#             from utilmeta.conf import Time
#             service.use(Time(
#                 use_tz=False
#                 # temporary fix problem: database connection isn't set to UTC on lower django version
#             ))


def setup_service(
    name,
    backend: str = None,
    async_param: Union[list, bool] = True,
):
    """
    If a list of params is provided, each param will not across and will execute in order
    for every ConfigParam, params inside are consider crossing, will enumerate every possible combination
    of the param
    """
    sys.path.extend([SERVICE_PATH])
    # os.chdir(SERVICE_PATH)

    # config_list = []
    # if PARAMETRIZE_CONFIG:
    #     for param in params:
    #         config_list.extend(param.generate_parametrized_configs())
    # if not config_list:
    #     from config.conf import config
    #     config_list = [config]

    async_params = None
    if isinstance(async_param, list):
        async_params = async_param
    elif async_param:
        async_params = [False, True]

    # if not backends:
    #     import django
    #     backends = [django]

    @pytest.fixture(
        scope='module',
        params=async_params,
        autouse=True,
        name='service'
    )
    def service(request):
        # from utilmeta import UtilMeta
        # srv = UtilMeta(
        #     name,
        #     name='tests',
        #     backend=request.param
        # )
        # srv.setup()
        from server import service
        if backend:
            service.set_backend(backend)
        if not service.backend:
            import django
            service.set_backend(django)
        if hasattr(request, 'param'):
            service.set_asynchronous(request.param)
        service.application()
        return service

    sys.modules[name or __name__].__dict__['service'] = service
    return service


# @pytest.fixture(scope="session")
# def available_port():
#     with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
#         s.bind(("", 0))
#         addr = s.getsockname()
#         port = addr[1]
#         return port


import threading
from django.core.servers.basehttp import (
    ThreadedWSGIServer,
    WSGIServer,
)  # noqa
from django.test.testcases import QuietWSGIRequestHandler  # noqa
# from asgiref.server import StatelessServer
# server = StatelessServer()
# from daphne.server import Server
from typing import Optional


class ServerThread(threading.Thread):
    def __init__(
        self,
        service: UtilMeta,
        *,
        connections_override=None,
        single_thread: bool = False,
    ):
        service._application = None
        self.service = service
        self.is_ready = threading.Event()
        self.error = None
        self.httpd: Optional[WSGIServer] = None
        # self.asgi: Optional[Server] = None
        self.connections_override = connections_override
        self.server_class = WSGIServer if single_thread else ThreadedWSGIServer
        self.host = self.service.host or '127.0.0.1'
        self.port = self.service.port
        super().__init__()

    def run(self):
        """
        Set up the live server and databases, and then loop over handling
        HTTP requests.
        """
        from django.db import connections
        if self.connections_override:
            # Override this thread's database connections with the ones
            # provided by the main thread.
            for alias, conn in self.connections_override.items():
                connections[alias] = conn

        # from a2wsgi import WSGIMiddleware
        try:
            # Create the handler for serving static and media files
            self.service._application = None
            self.service.adaptor = None
            self.service.set_backend(self.service.backend)
            app = self.service.application()
            # if self.service.asynchronous:
            #     self.asgi = Server(app)
            # else:
            self.httpd = self.server_class(
                (self.host, self.port),
                QuietWSGIRequestHandler,
                allow_reuse_address=False,
            )

            # if self.service.asynchronous:
            #     from a2wsgi import ASGIMiddleware
            #     app = ASGIMiddleware(app)
            self.httpd.set_app(app)

            self.is_ready.set()

            if self.httpd:
                self.httpd.serve_forever()
            # if self.asgi:
            #     self.asgi.run()
        except Exception as e:
            self.error = e
            self.is_ready.set()
        finally:
            connections.close_all()

    def terminate(self):
        if self.httpd:
            # Stop the WSGI server
            self.httpd.shutdown()
            self.httpd.server_close()
        # if self.asgi:
        #     self.asgi.stop()
        self.join(timeout=0)


def make_server_thread(backend, port: int = None, **kwargs):
    @pytest.fixture(scope="module")
    def server_thread(service: UtilMeta):
        service.set_backend(backend)
        if port:
            if service.asynchronous:
                service.port = int(f'1{port}')
            else:
                service.port = port
        else:
            service.resolve_port()

        thread = ServerThread(
            service, single_thread=True
        )
        thread.daemon = True
        thread.start()
        thread.is_ready.wait()
        if thread.error:
            raise thread.error
        yield thread
        # os.environ.pop("META_DISABLE_BACKGROUND_THREAD")
        thread.terminate()
    return server_thread


def make_live_thread(backend, port: int = None, **kwargs):
    @pytest.fixture(scope="module")
    def server_thread(service: UtilMeta):
        service.set_backend(backend)
        if port:
            if service.asynchronous:
                service.port = int(f'1{port}')
            else:
                service.port = port
        else:
            service.resolve_port()

        def run_service():
            print('RUN SERVICE')
            service.application()
            print('START RUN')
            service.run(**kwargs)

        from threading import Thread
        thread = Thread(target=run_service)
        thread.daemon = True
        thread.start()
        import socket
        cnt = 0
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            while True:
                if s.connect_ex(('127.0.0.1', service.port)) == 0:
                    break
                time.sleep(CONNECT_INTERVAL)
                cnt += 1
                if cnt > (CONNECT_TIMEOUT / CONNECT_INTERVAL):
                    return
        yield thread
        thread.join(timeout=0)
        # fixme: join thread won't terminate the inner http server
    return server_thread


def kill_child_processes(parent_pid, sig=signal.SIGTERM):
    try:
        parent = psutil.Process(parent_pid)
    except psutil.NoSuchProcess:
        return
    children = parent.children(recursive=True)
    for process in children:
        try:
            process.send_signal(sig)
            process.terminate()
        except psutil.Error:
            continue


def run_server(backend: str = None, port: int = None, asynchronous: bool = None):
    try:
        from pytest_cov.embed import cleanup_on_sigterm
    except ImportError:
        pass
    else:
        cleanup_on_sigterm()
    from server import service
    if backend:
        service.set_backend(backend)
    if port:
        service.port = port
    if asynchronous is not None:
        service.set_asynchronous(asynchronous)

    # from utilmeta.utils.schema.z_cov import cov
    # cov()
    # with open('./log', 'a') as f:
    #     f.write(f'=========================== SERVER RUN: {backend}, {port}, {asynchronous}\n')

    try:
        service.run()
    finally:
        from pytest_cov.embed import cleanup
        cleanup()


@ignore_errors
def clear_server_process(server):
    kill_child_processes(server.pid, signal.SIGTERM if WINDOWS else signal.SIGKILL)
    if WINDOWS:
        try:
            os.kill(server.pid, signal.SIGBREAK)
        except (PermissionError, OSError, WindowsError):
            pass
    else:
        server.terminate()


def make_live_process(backend: str = None, port: int = None, cmdline: bool = False):
    @pytest.fixture(scope="module")
    def service_process(service: UtilMeta):
        # env = os.environ.copy()
        # coverage = any([arg.startswith('coverage') or arg.startswith('--cov=') for arg in sys.argv])
        # warnings.warn(f'=======================COVERAGE: {coverage} {sys.argv}')

        try:
            from pytest_cov.embed import cleanup_on_sigterm
        except ImportError:
            pass
        else:
            cleanup_on_sigterm()
        import os
        if os.environ.get('DJANGO_SETTINGS_MODULE'):
            os.environ.pop('DJANGO_SETTINGS_MODULE')

        if port:
            if service.asynchronous:
                service.port = int(f'1{port}')
            else:
                service.port = port

        if cmdline:
            cmd = [sys.executable, os.path.join(SERVICE_PATH, 'server.py')]
            if backend or service.backend_name:
                cmd.append(f'--backend={backend or service.backend_name}')
            if service.asynchronous:
                cmd.append('--async')
            else:
                cmd.append('--sync')
            cmd.append(f'--port={str(service.port)}')
            server = subprocess.Popen(cmd, env=os.environ.copy(), cwd=os.getcwd())
        else:
            import multiprocessing
            server = multiprocessing.Process(target=run_server, args=(backend, service.port, service.asynchronous))
            server.start()
            #

        try:
            import socket
            cnt = 0
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                while True:
                    if s.connect_ex(('127.0.0.1', service.port)) == 0:
                        break
                    time.sleep(CONNECT_INTERVAL)
                    cnt += 1
                    if cnt > (CONNECT_TIMEOUT / CONNECT_INTERVAL):
                        return
            yield server
        finally:
            clear_server_process(server)
    return service_process


def make_cmd_process(file: Union[str, Path], *argv,
                     cwd: Union[str, Path] = None,
                     port: int = None):
    if not os.path.isabs(file):
        file = os.path.join(TEST_PATH, file)
    if not os.path.exists(file):
        raise FileExistsError(file)
    if cwd and not os.path.isabs(cwd):
        cwd = os.path.join(TEST_PATH, cwd)
    cmd = [sys.executable, str(file), *argv]
    # raise Exception(str(cmd))

    @pytest.fixture(scope="module")
    def command_process(db_using):
        import os
        if os.environ.get('DJANGO_SETTINGS_MODULE'):
            os.environ.pop('DJANGO_SETTINGS_MODULE')
        env = os.environ.copy()
        env['UTILMETA_OPERATIONS_DATABASE_ENGINE'] = db_using
        server = subprocess.Popen(cmd, env=env, cwd=str(cwd or os.getcwd()))
        try:
            if port:
                import socket
                cnt = 0
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    while True:
                        if s.connect_ex(('127.0.0.1', port)) == 0:
                            break
                        time.sleep(CONNECT_INTERVAL)
                        cnt += 1
                        if cnt > (CONNECT_TIMEOUT / CONNECT_INTERVAL):
                            return
            yield server
        finally:
            clear_server_process(server)

    return command_process
