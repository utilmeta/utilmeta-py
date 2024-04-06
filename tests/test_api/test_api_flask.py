from tests.conftest import make_live_process, setup_service, make_server_thread
from .params import do_live_api_tests
from utilmeta import UtilMeta

setup_service(__name__, backend='flask')
flask_server_process = make_live_process(backend='flask', port=8003, cmdline=True)
flask_server_thread = make_server_thread(backend='flask', port=8083)


def test_flask_api(service, flask_server_process):
    do_live_api_tests(service)
    service._application = None
    service.adaptor.app = None


def test_flask_api_internal(service: UtilMeta, flask_server_thread):
    do_live_api_tests(service)
    service._application = None
    service.adaptor.app = None


# def test_flask_api_internal_a(service: UtilMeta, flask_server_thread):
#     if not service.asynchronous:
#         return
#     do_live_api_tests(service)
