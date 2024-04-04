from typing import Union, List
import pytest
import sys
import os
import time
from utilmeta.utils import multi
from utilmeta import UtilMeta
# from django import VERSION as DJANGO_VERSION
SERVICE_PATH = os.path.join(os.path.dirname(__file__), 'server')
PARAMETRIZE_CONFIG = False
CONNECT_TIMEOUT = 3
CONNECT_INTERVAL = 0.1


def setup_service(name, backends: list = (), orm: str = None):
    """
    If a list of params is provided, each param will not across and will execute in order
    for every ConfigParam, params inside are consider crossing, will enumerate every possible combination
    of the param
    """
    sys.path.extend([SERVICE_PATH])
    os.chdir(SERVICE_PATH)

    # config_list = []
    # if PARAMETRIZE_CONFIG:
    #     for param in params:
    #         config_list.extend(param.generate_parametrized_configs())
    # if not config_list:
    #     from config.conf import config
    #     config_list = [config]

    if not backends:
        import django
        backends = [django]

    @pytest.fixture(
        scope='module',
        params=backends,
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
        if request.param:
            service.set_backend(request.param)
        service.application()
        return service

    sys.modules[name or __name__].__dict__['fixture_service'] = service
    return service


def make_live(service: UtilMeta, port=None):
    @pytest.fixture(scope="session")
    def server_thread():
        if port:
            service.port = port

        def run_service():
            service.application()
            service.run()

        from threading import Thread
        thread = Thread(target=run_service)
        thread.daemon = True
        thread.start()
        import socket
        cnt = 0
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            while True:
                if s.connect_ex((service.host, service.port)) == 0:
                    break
                time.sleep(CONNECT_INTERVAL)
                cnt += 1
                if cnt > (CONNECT_TIMEOUT / CONNECT_INTERVAL):
                    return
        yield thread
        thread.join(timeout=0)
    return server_thread
