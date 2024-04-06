from tests.conftest import setup_service, make_live_process, make_server_thread
from .params import do_live_api_tests


setup_service(__name__, backend='django')
django_server_process = make_live_process(
    backend='django',
    port=8001
)
django_server_thread = make_server_thread(
    backend='django',
    port=8081
)


def test_django_api(service, django_server_process):
    do_live_api_tests(service)


def test_django_api_internal(service, django_server_thread):
    if service.asynchronous:
        return
    do_live_api_tests(service)
