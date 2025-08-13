from tests.conftest import make_live_process, setup_service, make_live_thread
from .params import do_live_api_tests, do_live_api_sse_tests
import sys

if sys.version_info >= (3, 9):
    setup_service(__name__, backend='sanic')
    sanic_server_process = make_live_process(backend='sanic', port=8004, cmdline=True)
    # sanic_server_thread = make_live_thread(backend='sanic', port=8084)
    from sanic import Sanic
    Sanic._app_registry = {}


    def test_sanic_api(service, sanic_server_process):
        do_live_api_tests(service)

        if service.asynchronous:
            do_live_api_sse_tests(port=18004 if service.asynchronous else 8004, asynchronous=False)
            do_live_api_sse_tests(port=18004 if service.asynchronous else 8004, asynchronous=True)
            # sanic error: sanic.exceptions.ServerError: Attempted response to unknown request
            # but not interfere the result

        service._application = None
        service.adaptor.app = None
        Sanic._app_registry = {}

    # def test_sanic_api_internal(service, sanic_server_thread):
    #     do_live_api_tests(service)
