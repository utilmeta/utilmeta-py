"""
WSGI config for django_demo project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application
import sys
from tests.conftest import get_operations_db
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_demo.settings")

application = get_wsgi_application()

from utilmeta.ops import Operations
Operations(
    route='ops',
    database=get_operations_db(),
    base_url='http://127.0.0.1:9091',
    eager_migrate=True   # eager migration for test
).integrate(application, __name__)
