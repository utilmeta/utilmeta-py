from tests.conftest import make_live_process, setup_service, make_live_thread
from .params import do_live_api_tests

setup_service(__name__, backend='fastapi', async_param=[True])
# FastAPI (starlette) can have bad response to a full-sync context, so we only test the asynchronous version
fastapi_server_process = make_live_process(backend='fastapi', port=8002)
fastapi_server_thread = make_live_thread(
    backend='fastapi',
    port=8082
)


def test_fastapi_api(service, fastapi_server_process):
    do_live_api_tests(service)
    service._application = None
    service.adaptor.app = None


def test_fastapi_api_internal(service, fastapi_server_thread):
    do_live_api_tests(service)
    service._application = None
    service.adaptor.app = None
