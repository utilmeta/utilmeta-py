from .plugins.atomic import AtomicPlugin as Atomic

# from .plugins.relate import Relate
from .fields import *
from .schema import Schema, Query, QueryContext
from .backends.base import ModelAdaptor
from .databases.config import DatabaseConnections, Database
from .exceptions import *

# class P:
#     # a placeholder to combined with
#     pass


from utype import Options

W = Options(mode="w", override=True)
WP = Options(mode="w", ignore_required=True, override=True)
A = Options(mode="a", override=True)
R = Options(mode="r", override=True)
