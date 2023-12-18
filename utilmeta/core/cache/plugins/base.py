from utilmeta.utils.plugin import Plugin
from utilmeta.utils import multi, get_interval, map_dict, keys_or_args, time_now, fast_digest, COMMON_TYPES
from typing import Union, Optional, Dict, Any, List, Type, TYPE_CHECKING
from datetime import datetime, timedelta
from ..lock import BaseLocker
from ..config import CacheConnections

if TYPE_CHECKING:
    from .entity import CacheEntity

NUM_TYPES = (int, float)
NUM = Union[int, float]
VAL = Union[str, bytes, list, tuple, dict]

__all__ = ['BaseCacheInterface']


class BaseCacheInterface(Plugin):
    OBSOLETE_LRU = 'LRU'  # least recently updated
    OBSOLETE_LFU = 'LFU'  # least frequently used
    OBSOLETE_RANDOM = 'RANDOM'

    def __init__(self, cache_alias: str = 'default', *,
                 scope_prefix: str = None,
                 max_entries: int = None,  # None means unlimited
                 max_entries_policy: str = OBSOLETE_LFU,
                 max_entries_tolerance: int = 0,
                 # if vary is specified, max_entries is relative to each variant
                 max_variants: int = None,
                 max_variants_policy: str = OBSOLETE_LFU,
                 max_variants_tolerance: int = 0,
                 trace_keys: bool = None,
                 default_timeout: Union[int, float, timedelta] = None,
                 lock_timeout: Union[int, float, timedelta] = None,
                 lock_blocking_timeout: Union[int, float, timedelta] = None,
                 entity_cls: Type['CacheEntity'] = None,
                 document: str = None,
                 **kwargs
                 ):
        super().__init__(locals())

        if max_entries:
            assert isinstance(max_entries, int) and max_entries >= 0, \
                f'Invalid expose Cache max_entries: {max_entries}' \
                f', must be an int >= 0 (max_entries=0 means no store)'

        if scope_prefix is not None:
            assert isinstance(scope_prefix, str), f'Cache.scope_prefix must be a str, got {scope_prefix}'

        if max_entries or max_variants:
            # in order to implement max_entries and max_variants, we must enable trace_keys
            # to track the keys hit count and last_modified
            trace_keys = True

        self.trace_keys = trace_keys
        self.max_entries = max_entries
        self.max_entries_policy = max_entries_policy
        self.max_entries_tolerance = max_entries_tolerance
        self.max_variants = max_variants
        self.max_variants_policy = max_variants_policy
        self.max_variants_tolerance = max_variants_tolerance

        from .entity import CacheEntity
        if entity_cls:
            assert issubclass(entity_cls, CacheEntity), \
                f'Cache.entity_cls must inherit from CacheEntity, got {entity_cls}'
        self.entity_cls = entity_cls or CacheEntity

        self.default_timeout = get_interval(default_timeout, null=True)
        self.lock_timeout = get_interval(lock_timeout, null=True)
        self.lock_blocking_timeout = get_interval(lock_blocking_timeout, null=True)
        self._scope_prefix = scope_prefix
        self._service_prefix = ''
        self._cache_alias = cache_alias

    @property
    def cache_alias(self):
        return self._cache_alias

    @property
    def cache_instance(self):
        return CacheConnections.get(self.cache_alias)

    # @property
    # def redis_con(self):
    #     if self.cache_config and self.cache_config.is_redis:
    #         return self.cache_config.get_redis_connection(alias=self.cache_alias)
    #     return None

    @property
    def scope_prefix(self) -> str:
        if self._scope_prefix is not None:
            # can take empty scope prefix, which will gain access to the global scope
            return self._scope_prefix
        return self.__ref__ or ''

    @property
    def variant(self):
        return None

    @property
    def varied(self) -> bool:
        return False

    @property
    def base_key_prefix(self):
        # not varied
        return '-'.join([v for v in [self._service_prefix, self.scope_prefix] if v])

    def encode(self, key: VAL, _con: str = '-', _variant=None):
        """
        Within the same scope, you can use different connector (1 length) to identify some sub-key-domains
        currently using
        * "-": default, when user call native cache api like self.cache.set(key)
        * "@": inner, like last_modified key, scope keys-count key
        * ":": using to store cached
        """
        if isinstance(key, bytes):
            key = key.decode()
        elif multi(key):
            return [self.encode(k, _con, _variant) for k in key]
        elif isinstance(key, dict):
            return {self.encode(k, _con, _variant): v for k, v in key.items()}
        else:
            key = str(key)
        if not isinstance(_con, str) or len(_con) != 1:
            _con = '-'
        if _variant:
            prefix = f'{self.base_key_prefix}-{_variant}'
        else:
            prefix = self.base_key_prefix
        if key.startswith(prefix):
            return key
        return f'{prefix}{_con}{key}'

    def decode(self, key: VAL, _variant=None):
        if isinstance(key, bytes):
            key = key.decode()
        elif multi(key):
            return [self.decode(k, _variant) for k in key]
        elif isinstance(key, dict):
            return {self.decode(k, _variant): v for k, v in key.items()}
        else:
            key = str(key)
        if _variant:
            prefix = f'{self.base_key_prefix}-{_variant}'
        else:
            prefix = self.base_key_prefix
        if key.startswith(prefix):
            return key[len(prefix) + 1:]
        return key

    def __getitem__(self, item):
        return self.get(item)

    def __setitem__(self, key, value):
        return self.set(key, value)

    def __eq__(self, other: 'BaseCacheInterface'):
        if not isinstance(other, BaseCacheInterface):
            return False
        return self.scope_prefix == other.scope_prefix

    def get(self, key, default=None):
        entity = self.get_entity()
        v = entity.get(self.encode(key), single=True)
        if v is None:
            return default
        return v

    def fetch(self, args=None, *keys, named: bool = False) -> Union[list, Dict[str, Any]]:
        keys = keys_or_args(args, *keys)
        entity = self.get_entity()
        values = entity.get(*self.encode(keys))
        return map_dict(values, *keys) if named else values

    def get_last_modified(self, args=None, *keys) -> Optional[datetime]:
        keys = keys_or_args(args, *keys)
        entity = self.get_entity()
        return entity.last_modified(*self.encode(keys))

    def get_entity(self, readonly: bool = False, variant=None) -> 'CacheEntity':
        return self.entity_cls(self, readonly=readonly, variant=variant)

    def set(self, key, value, *, timeout: Union[int, timedelta, datetime] = ...,
            exists_only: bool = False, not_exists_only: bool = False):
        entity = self.get_entity()
        entity.set(self.encode(key), value, timeout=self.get_timeout(timeout),
                   exists_only=exists_only, not_exists_only=not_exists_only)

    def pop(self, key):
        val = self[key]
        del self[key]
        return val

    def delete(self, args=None, *keys):
        keys = keys_or_args(args, *keys)
        if not keys:
            return
        entity = self.get_entity()
        entity.delete(*self.encode(keys))

    def clear(self):
        entity = self.get_entity()
        entity.clear()

    def clear_variants(self, *variants):
        for variant in variants:
            entity = self.get_entity(variant=variant)
            entity.clear()

    def get_variants(self):
        if not self.varied:
            return []
        entity = self.get_entity()
        return entity.variants()

    def clear_all(self):
        if self.varied:
            self.clear_variants(*self.get_variants())
        else:
            return self.clear()

    def reset_stats(self):
        entity = self.get_entity()
        entity.reset_stats()

    def reset_variants_stats(self, *variants):
        for variant in variants:
            entity = self.get_entity(variant=variant)
            entity.reset_stats()

    def reset_all_stats(self):
        if self.varied:
            self.reset_variants_stats(*self.get_variants())
        else:
            return self.reset_stats()

    def __delitem__(self, key):
        self.delete(key)

    def has(self, key) -> bool:
        return bool(self.exists(key))

    @property
    def keys(self) -> List[str]:
        entity = self.get_entity()
        return self.decode(entity.keys())

    @property
    def count(self) -> int:
        entity = self.get_entity()
        return entity.count()

    def __len__(self) -> int:
        return self.count

    def exists(self, args=None, *keys) -> int:
        keys = keys_or_args(args, *keys)
        if not keys:
            return 0
        entity = self.get_entity()
        return entity.exists(*self.encode(keys))

    def __contains__(self, key) -> bool:
        return self.has(key)

    def expire(self, *keys: str, timeout: float):
        entity = self.get_entity()
        entity.expire(*self.encode(keys), timeout=self.get_timeout(timeout))

    def update(self, data: Dict[str, Any], timeout: Union[int, timedelta, datetime] = ...):
        if not data:
            return
        entity = self.get_entity()
        entity.update(data=self.encode(data), timeout=self.get_timeout(timeout))

    def incr(self, key: str, amount: NUM = 1, upper_bound: int = None) -> Optional[NUM]:
        """
        Increase key by amount > 0, you can set a high_bound number
        return the altered number (float/int) if successfully modified, elsewhere return None
        """
        if not amount:
            return self[key]
        if amount < 0:
            raise ValueError(f'Cache incr amount should > 0, got {amount}')
        return self.alter(key=key, amount=amount, limit=upper_bound)

    def decr(self, key: str, amount: NUM = 1, lower_bound: int = None) -> Optional[NUM]:
        """
           Decrease key by amount > 0, you can set a low_bound number
           return the altered number (float/int) if successfully modified, elsewhere return None
        """
        if not amount:
            return self[key]
        if amount < 0:
            raise ValueError(f'Cache decr amount should > 0, got {amount}')
        return self.alter(key=key, amount=-amount, limit=lower_bound)

    def alter(self, key: str, amount: Union[int, float], limit: int = None) -> Optional[NUM]:
        entity = self.get_entity()
        return entity.alter(self.encode(key), amount=amount, limit=limit)

    def lock(self, args=None, *keys, block: bool = False) -> BaseLocker:
        keys = keys_or_args(args, *keys)
        entity = self.get_entity()
        return entity.lock(*keys, block=block)

    def get_stats(self):
        """
        . total keys
        . total visits, key visits
        . response cache hit ratio (hits/miss)
        . variants (keys and visits for each variants)
        . max_entries policy trigger
        :return:
        """
        if not self.trace_keys:
            raise NotImplementedError(f'Cache.get_stats not implemented, '
                                      f'please set trace_keys=True to enable this method')

        requests = 0
        total_hits = 0
        total_keys = 0
        last_modified = None
        last_modified_list = []

        variant_data = []
        if self.varied:
            for variant in self.get_variants():
                var_entity = self.get_entity(variant=variant)
                req = var_entity.get_requests()
                hits = var_entity.get_total_hits()
                last_mod = var_entity.get_latest_update()
                size = var_entity.count()
                requests += req
                total_hits += hits
                total_keys += size
                if last_mod:
                    last_modified_list.append(last_mod)
                variant_data.append({
                    'variant': variant,
                    'requests': req,
                    'hits': hits,
                    'size': size,
                    'last_modified': last_mod
                })
            if last_modified_list:
                last_modified = max(last_modified_list)
        else:
            entity = self.get_entity()
            requests = entity.get_requests()
            total_keys = entity.count()
            total_hits = entity.get_total_hits()
            last_modified = entity.get_latest_update()

        return {
            'scope_prefix': self.scope_prefix,
            'max_entries': self.max_entries,
            'max_variants': self.max_variants,
            'requests': requests,
            'hits': total_hits,
            'size': total_keys,
            'last_modified': last_modified,
            'variants': variant_data
        }

    @classmethod
    def get_seconds(cls, timeout):
        if isinstance(timeout, datetime):
            timeout = timeout - time_now()
        if isinstance(timeout, timedelta):
            timeout = timeout.total_seconds()
        if isinstance(timeout, int) and timeout >= 0:
            return timeout
        return None

    def get_timeout(self, timeout: Union[int, timedelta, datetime, float] = ...):
        if timeout is ...:
            timeout = self.default_timeout
        if timeout is not None:
            timeout = self.get_seconds(timeout)
        return timeout

    @classmethod
    def dump_kwargs(cls, **kwargs) -> str:
        """
        dump the args & kwargs of a callable to a comparable string
        use for API cache
        """
        def dump_data(data) -> str:
            if multi(data):
                if isinstance(data, set):
                    data = list(data)
                    try:
                        # the order of set data doesn't matter
                        data.sort()
                    except TypeError:
                        pass
                lst = []
                for d in data:
                    lst.append(dump_data(d))
                return '[%s]' % ','.join(lst)
            elif isinstance(data, dict):
                lst = []
                for k in sorted(data.keys()):
                    lst.append(f'{repr(k)}:{dump_data(data[k])}')
                return '{%s}' % ','.join(lst)
            elif isinstance(data, COMMON_TYPES):
                return repr(data)
            return str(data)
        # even if args and kwargs are empty, still get a equal length key
        return fast_digest(
            dump_data(kwargs),
            compress=False,
            consistent=True,
        )
