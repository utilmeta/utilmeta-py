from .base import API
from .base import APIRef as ref
from .decorator import *
from . import decorator
from .plugins.base import APIPlugin as Plugin
from .plugins.retry import RetryPlugin as Retry
from .plugins.cors import CORSPlugin as CORS
from .plugins.cache import HttpCache as Cache

# from .plugins.rate import RateLimitPlugin as RateLimit

route = decorator.APIDecoratorWrapper(None)
get = decorator.APIDecoratorWrapper("get")
put = decorator.APIDecoratorWrapper("put")
post = decorator.APIDecoratorWrapper("post")
patch = decorator.APIDecoratorWrapper("patch")
delete = decorator.APIDecoratorWrapper("delete")
# below is SDK-only method
head = decorator.APIDecoratorWrapper("head")
options = decorator.APIDecoratorWrapper("options")
trace = decorator.APIDecoratorWrapper("trace")
