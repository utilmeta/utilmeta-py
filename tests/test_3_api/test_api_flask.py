from tests.conftest import make_live_process, setup_service, make_server_thread
from .params import do_live_api_tests, do_live_api_sse_tests
from utilmeta import UtilMeta
import sys
import asyncio

setup_service(__name__, backend='flask', async_param=[False, True])
flask_server_process = make_live_process(backend='flask', port=8003, cmdline=True)
flask_server_thread = make_server_thread(backend='flask', port=8083)


if sys.platform == "win32" and sys.version_info >= (3, 8, 0):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def test_flask_api(service, flask_server_process):
    service._application = None
    service.adaptor.app = None
    do_live_api_tests(service)
    do_live_api_sse_tests(port=18003 if service.asynchronous else 8003, asynchronous=False)
    # flask cannot handle async sse
    service._application = None
    service.adaptor.app = None


def test_flask_api_internal(service: UtilMeta, flask_server_thread):
    service._application = None
    service.adaptor.app = None
    do_live_api_tests(service)
    service._application = None
    service.adaptor.app = None


# def test_flask_api_internal_a(service: UtilMeta, flask_server_thread):
#     if not service.asynchronous:
#         return
#     do_live_api_tests(service)
