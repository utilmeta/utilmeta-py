from utype.types import *
from utilmeta.utils.plugin import Plugin
from utilmeta.utils import Header
from utilmeta.core.request import Request


class RateLimitPlugin(Plugin):
    @classmethod
    def ban_user(cls, request: 'Request'):
        return request.user_id

    @classmethod
    def ban_ip(cls, request: 'Request'):
        return request.ip

    @classmethod
    def ban_session(cls, request: 'Request'):
        return request.session.session_key

    @classmethod
    def ban_origin(cls, request: 'Request'):
        return request.origin

    @classmethod
    def ban_agent(cls, request: 'Request'):
        return request.ua_string

    @classmethod
    def ban_referrer(cls, request: 'Request'):
        return request.headers.get(Header.REFERER)

    def __init__(self,
                 max_rps: Union[int, float] = None,
                 max_times: int = None,
                 max_errors: int = None,
                 cache_alias: str = None,
                 reset_after: Union[int, timedelta, float] = None,
                 cycle_start: datetime = None,
                 cycle_interval: datetime = None,
                 ban_function: Callable = None):
        super().__init__(locals())
