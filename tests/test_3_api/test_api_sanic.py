from tests.conftest import make_live_process, setup_service, make_live_thread
from .params import do_live_api_tests

setup_service(__name__, backend='sanic')
sanic_server_process = make_live_process(backend='sanic', port=8004, cmdline=True)
# sanic_server_thread = make_live_thread(backend='sanic', port=8084)
from sanic import Sanic
Sanic._app_registry = {}


def test_sanic_api(service, sanic_server_process):
    do_live_api_tests(service)
    service._application = None
    service.adaptor.app = None
    Sanic._app_registry = {}

# def test_sanic_api_internal(service, sanic_server_thread):
#     do_live_api_tests(service)
