import django

from tests.conftest import setup_service, make_live_process, make_server_thread
from .params import do_live_api_tests, do_live_api_sse_tests


setup_service(__name__, backend='django')
django_server_process = make_live_process(
    backend='django',
    port=8001,
    cmdline=True
)
django_server_thread = make_server_thread(
    backend='django',
    port=8081
)


def test_django_api(service, django_server_process):
    if django.VERSION < (3, 1) and service.asynchronous:
        return
    do_live_api_tests(service)
    if django.VERSION >= (4, 0):
        do_live_api_sse_tests(
            port=18001 if service.asynchronous else 8001,
            asynchronous=False,
            with_timeout=not service.asynchronous
        )
        do_live_api_sse_tests(
            port=18001 if service.asynchronous else 8001,
            asynchronous=True,
            with_timeout=service.asynchronous
        )
    service._application = None
    service.adaptor.app = None


def test_django_api_internal(service, django_server_thread):
    if service.asynchronous:
        return
    do_live_api_tests(service)
    service._application = None
    service.adaptor.app = None
