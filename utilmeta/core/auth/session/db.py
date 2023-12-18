from .schema import BaseSessionSchema, SessionCreateError, SessionUpdateError
from utilmeta.conf.database import DatabaseConnections, Database
from .base import BaseSession
from utilmeta.utils import awaitable


# class DBSessionSchema(BaseSessionSchema):
#     __connections_cls__ = DatabaseConnections
#
#     def get_db(self) -> Database:
#         return self.__connections_cls__.get(self._config.db_alias)
#
#     @property
#     def cache_key_prefix(self):
#         common_prefix = f'{self.__class__.__module__}'
#         key_prefix = self._config.key_prefix or ''
#         return f'{common_prefix}{key_prefix}'
#
#     def get_key(self, session_key: str = None) -> str:
#         return self.cache_key_prefix + (session_key or self._session_key or self._get_new_session_key())
#
#     def exists(self, session_key: str) -> bool:
#         if not session_key:
#             return False
#         cache = self.get_cache()
#         return bool(cache.exists(session_key))
#
#     @awaitable(exists)
#     async def exists(self, session_key: str) -> bool:
#         if not session_key:
#             return False
#         cache = self.get_cache()
#         return bool(await cache.exists(session_key))
#
#     def create(self):
#         self._session_key = self._get_new_session_key()
#         try:
#             self.save(must_create=True)
#         except SessionCreateError:
#             return
#         self._modified = True
#         return
#
#     @awaitable(create)
#     async def create(self):
#         self._session_key = self._get_new_session_key()
#         try:
#             await self.save(must_create=True)
#         except SessionCreateError:
#             return
#         self._modified = True
#         return
#
#     def save(self, must_create: bool = False):
#         if self.session_key is None:
#             return self.create()
#         cache = self.get_cache()
#         if not must_create:
#             if cache.get(self.get_key()) is None:
#                 raise SessionUpdateError
#         result = cache.set(self.get_key(), dict(self), not_exists_only=must_create, timeout=self.expiry_age)
#         if must_create and not result:
#             raise SessionCreateError
#
#     @awaitable(save)
#     async def save(self, must_create: bool = False):
#         if self.session_key is None:
#             return await self.create()
#         cache = self.get_cache()
#         if not must_create:
#             if await cache.get(self.get_key()) is None:
#                 raise SessionUpdateError
#         result = await cache.set(self.get_key(), dict(self), not_exists_only=must_create, timeout=self.expiry_age)
#         if must_create and not result:
#             raise SessionCreateError
#
#     def delete(self, session_key: str = None):
#         if session_key is None:
#             if self.session_key is None:
#                 return
#             session_key = self.session_key
#         self.get_cache().delete(self.get_key(session_key))
#
#     @awaitable(delete)
#     async def delete(self, session_key: str = None):
#         if session_key is None:
#             if self.session_key is None:
#                 return
#             session_key = self.session_key
#         await self.get_cache().delete(self.get_key(session_key))
#
#     def load(self):
#         try:
#             session_data = self.get_cache().get(self.get_key())
#         except Exception:
#             # Some backends (e.g. memcache) raise an exception on invalid
#             # cache keys. If this happens, reset the session. See #17810.
#             session_data = None
#         if session_data is not None:
#             return session_data
#         self._session_key = None
#         return {}
#
#     @awaitable(load)
#     async def load(self):
#         try:
#             session_data = await self.get_cache().get(self.get_key())
#         except Exception:
#             # Some backends (e.g. memcache) raise an exception on invalid
#             # cache keys. If this happens, reset the session. See #17810.
#             session_data = None
#         if session_data is not None:
#             return session_data
#         self._session_key = None
#         return {}
#
#
# class AdvancedSession(BaseSession):
#     def __init__(self,
#                  cluster_scope: bool = False,
#                  from_service: str = None,
#                  cycle_key_at_login: bool = True,
#                  verify_ip_identical: Union[bool, Callable] = False,
#                  verify_ua_identical: Union[bool, Callable] = False,
#                  limit_per_user: Union[int, Callable] = None,
#                  user_preemptive: Union[bool, Callable] = None,
#                  user_expiry_age: Union[int, timedelta, Callable] = None,
#                  # ignore_db_error: bool = False,
#                  human_ua_only: bool = None,
#                  public_ip_only: bool = None, **kwargs):
#         super().__init__(**locals())
#         self.human_ua_only = human_ua_only
#         self.public_ip_only = public_ip_only
#
#         self.verify_ip_identical = verify_ip_identical
#         self.verify_ua_identical = verify_ua_identical
#         if user_preemptive is not None and not limit_per_user:
#             raise ValueError(f'Session.user_preemptive only works when Session.limit_per_user is set')
#
#         self.user_preemptive = user_preemptive
#
#         if limit_per_user is not None:
#             # assert self.use_db, f'Session.user_max_session enable requires to use engine in' \
#             #                     f' {[self.DB, self.CACHED_DB, self.CLUSTER_CACHED_DB]}, got {self.engine}'
#
#             assert callable(limit_per_user) or isinstance(limit_per_user, int) and limit_per_user > 0, \
#                 f'Session.user_max_session must be a callable or a positive integer, got {limit_per_user}'
#
#         self.limit_per_user = limit_per_user
#         self.expiry_age = user_expiry_age
#
#         # if cluster_scope:
#         #     # assert cookie.cross_domain, f'Session with cluster_scope=True require to turn Cookie(cross_domain=True)'
#         #     if self.engine not in (self.COOKIE, self.CLUSTER_CACHE, self.CLUSTER_CACHED_DB):
#         #         raise ValueError('Session(cluster_scope=True) only support cross_'
#         #                          'domain Cookie and clustered Cache backend')
#
#         self.cluster_scope = cluster_scope
#         self.cycle_key_at_login = cycle_key_at_login
#         self.from_service = from_service
