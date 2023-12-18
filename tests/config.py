from typing import Union, List
import pytest
import sys
import os
from utilmeta.utils import multi
from utilmeta import conf
# from django import VERSION as DJANGO_VERSION
SERVICE_PATH = os.path.join(os.path.dirname(__file__), 'server')
PARAMETRIZE_CONFIG = False


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
