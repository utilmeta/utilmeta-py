from tests.conftest import make_live_process, setup_service, make_live_thread
from .params import do_live_api_tests

setup_service(__name__, backend='tornado')
tornado_server_process = make_live_process(backend='tornado', port=8005)
tornado_server_thread = make_live_thread(backend='tornado', port=8085)


def test_tornado_api(service, tornado_server_process):
    do_live_api_tests(service)
    service._application = None
    service.adaptor.app = None


def test_tornado_api_internal(service, tornado_server_thread):
    do_live_api_tests(service)
    service._application = None
    service.adaptor.app = None
