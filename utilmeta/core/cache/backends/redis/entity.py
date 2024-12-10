from utype.types import *
from utype import type_transform
from ...plugins.entity import CacheEntity
from utilmeta.utils import dumps, loads, normalize, get_number, COMMON_ERRORS, utc_ms_ts
from redis.exceptions import ResponseError
from redis.client import Redis
from .scripts import *
from .lock import RedisLocker
import random

NUM_TYPES = (int, float)


class RedisCacheEntity(CacheEntity):
    backend_name = "redis"

    @property
    def con(self) -> Redis:
        return Redis.from_url(self.cache.get_location())

    def get_requests(self):
        req = self.con.get(self.requests_key)
        if not req:
            return 0
        return int(req.decode())

    def reset_stats(self):
        self.con.set(self.requests_key, 0)
        self.con.delete(self.hits_key)

    def keys(self):
        if not self.src.trace_keys:
            raise NotImplementedError(
                f"Cache.keys not implemented, "
                f"please set trace_keys=True to enable this method"
            )
        tot_keys: List[bytes] = self.con.zrange(self.update_key, 0, -1)
        if not tot_keys:
            return []
        misses = self.con.eval(BATCH_EXISTS_LUA, len(tot_keys), *tot_keys, 0)
        if misses:
            self.con.zrem(self.hits_key, *misses)
            self.con.zrem(self.update_key, *misses)
            tot_keys = list(set(tot_keys).difference(misses))
        return [v.decode() for v in tot_keys]

    def get_total_hits(self):
        pairs = self.con.zrange(self.hits_key, 0, -1, withscores=True)
        if not pairs:
            return 0
        scores = 0
        for val, score in pairs:
            scores += score
        return scores

    def get_key_hits(self, *keys):
        scores = 0
        for key in keys:
            scores += self.con.zscore(self.hits_key, key) or 0
        return scores

    def get_latest_update(self):
        max_pair = self.con.zrange(self.update_key, 0, 1, desc=True, withscores=True)
        if not max_pair:
            return None
        return type_transform(max_pair[0][1], datetime)

    def last_modified(self, *keys: str) -> Optional[datetime]:
        if not self.src.trace_keys:
            raise NotImplementedError(
                f"Cache.last_modified not implemented, "
                f"please set trace_keys=True to enable this method"
            )
        times = []
        for key in keys:
            sc = self.con.zscore(self.update_key, key)
            if sc:
                times.append(sc)
        if times:
            return type_transform(max(times), datetime)
        return None

    def clear(self):
        if not self.src.trace_keys:
            raise NotImplementedError(
                f"Cache.clear not implemented, "
                f"please set trace_keys=True to enable this method"
            )
        keys = [v.decode() for v in self.con.zrange(self.update_key, 0, -1)]
        # do not need to validate exists now
        self.con.delete(*keys, self.requests_key, self.update_key, self.hits_key)
        if self.variant:
            # clear for this vary
            self.con.zrem(self.vary_hits_key, self.variant)
            self.con.zrem(self.vary_update_key, self.variant)

    def delete(self, *keys: str):
        if not keys:
            return
        if self.readonly:
            raise RuntimeError(f"Attempt to delete key ({keys}) at a readonly cache")

        # upd_keys = self.last_update_key(keys)
        self.con.delete(*keys)

        if self.src.trace_keys:
            self.con.zrem(
                self.hits_key, *keys
            )  # remove deleted keys from hit statistics
            self.con.zrem(
                self.update_key, *keys
            )  # remove deleted keys from last update

    def count(self) -> int:
        if not self.src.trace_keys:
            raise NotImplementedError(
                f"Cache.keys not implemented, "
                f"please set trace_keys=True to enable this method"
            )
        # return self.con.zcard(self.total_key)
        # consider key timeout, we cannot cat the accurate exists metrics from total key only
        tot_keys = self.con.zrange(self.update_key, 0, -1)
        return self.con.exists(*tot_keys) if tot_keys else 0

    def exists(self, *keys: str) -> int:
        return self.con.exists(*keys)

    def alter(
        self, key: str, amount: Union[int, float], limit: Union[int, float] = None
    ):
        if self.readonly:
            return None
        self.prepare(key)
        argv = [amount, limit] if isinstance(limit, NUM_TYPES) else [amount]
        result: Optional[bytes] = self.con.eval(ALTER_AMOUNT_LUA, 1, key, *argv)

        if self.src.trace_keys:
            self.con.incr(self.requests_key, 1)
            if result is not None:
                self.z_incr_by(self.hits_key, key)
                if self.variant:
                    self.z_incr_by(self.vary_hits_key, self.variant)

        if result is None:
            return None
        if isinstance(result, NUM_TYPES):
            return result
        if isinstance(result, bytes):
            result = result.decode()  # noqa
        return get_number(result)  # noqa

    def lock(self, *keys: str, block: bool = False):
        return RedisLocker(
            self.con,
            *keys,
            block=block,
            timeout=self.src.lock_timeout,
            blocking_timeout=self.src.lock_blocking_timeout,
        )

    def lpush(self, key: str, *values):
        if not values:
            return
        if self.readonly:
            raise PermissionError(
                f"Attempt to lpush ({key} -> {values}) to a readonly cache"
            )
        res = self.con.lpush(key, *values)
        if self.src.trace_keys:
            self.con.zadd(self.update_key, {key: utc_ms_ts()})
        return res

    def rpush(self, key: str, *values):
        if not values:
            return
        if self.readonly:
            raise PermissionError(
                f"Attempt to rpush ({key} -> {values}) to a readonly cache"
            )
        res = self.con.rpush(key, *values)
        if self.src.trace_keys:
            self.con.zadd(self.update_key, {key: utc_ms_ts()})
        return res

    def lpop(self, key: str):
        if self.readonly:
            raise PermissionError(f"Attempt to lpop ({key}) to a readonly cache")
        res = self.con.lpop(key)
        if self.src.trace_keys:
            self.con.zadd(self.update_key, {key: utc_ms_ts()})
        return res

    def rpop(self, key: str):
        if self.readonly:
            raise PermissionError(f"Attempt to rpop ({key}) to a readonly cache")
        res = self.con.rpop(key)
        if self.src.trace_keys:
            self.con.zadd(self.update_key, {key: utc_ms_ts()})
        return res

    def z_incr_by(self, name, key, value=1.0):
        """
        Even name and key does not exists
        """
        try:
            self.con.zincrby(name, float(value), key)  # add hit times
        except ResponseError:
            # different backend version may cause error
            self.con.zincrby(name, key, float(value))

    def get(self, *keys: str, single: bool = False):
        if not keys:
            if single:
                return None
            return []

        hits = []
        if single:
            result = self.con.get(keys[0])
            if result is not None:
                hits = keys
        else:
            result = self.con.mget(*keys)
            hits = [k for k in keys if k in result]

        if self.src.trace_keys:
            self.con.incr(self.requests_key, len(keys))

            for hit in hits:
                self.z_incr_by(self.hits_key, hit)
            if self.variant:
                self.z_incr_by(self.vary_hits_key, self.variant)

        result = loads(result, exclude_types=NUM_TYPES, bulk_data=not single)
        if not result:
            return result
        return result

    def prepare(self, *keys: str):
        if not keys:
            return

        if not self.src.trace_keys:
            return

        last_modified = utc_ms_ts()

        if self.src.max_entries:
            # key have not been set
            current_keys = self.con.zrange(self.update_key, 0, -1)
            excess: int = self.exists(*current_keys, *keys) - self.src.max_entries

            if (
                excess > self.src.max_entries_tolerance
            ):  # default to 0, but can set a throttle value
                # total_key >= max_entries
                # delete the least frequently hit key
                target_key = None
                del_keys = []
                if self.src.max_entries_policy == self.src.OBSOLETE_LFU:
                    target_key = self.hits_key
                elif self.src.max_entries_policy == self.src.OBSOLETE_LRU:
                    target_key = self.update_key
                elif self.src.max_entries_policy == self.src.OBSOLETE_RANDOM:
                    exists_keys = self.keys()
                    del_keys = random.choices(exists_keys, k=excess)

                if target_key:
                    try:
                        del_keys = [
                            items[0] for items in self.con.zpopmin(target_key, excess)
                        ]
                    except (ResponseError, *COMMON_ERRORS):
                        # old version of redis or windows not support this command, downgrade
                        for k in self.con.zrange(target_key, 0, -1):
                            if self.con.zrank(target_key, k) < excess:
                                del_keys.append(k)

                if del_keys:
                    self.delete(*del_keys)

        if self.variant:
            self.con.zadd(self.vary_hits_key, {self.variant: 0}, nx=True)
            self.con.zadd(self.vary_update_key, {self.variant: last_modified})

            if self.src.max_variants:
                excess = self.con.zcard(self.vary_hits_key) - self.src.max_variants

                if (
                    excess > self.src.max_variants_tolerance
                ):  # default to 0, but can set a throttle value
                    # total_key >= max_entries
                    # delete the least frequently hit key
                    target_key = None
                    del_keys = []
                    if self.src.max_variants_tolerance == self.src.OBSOLETE_LFU:
                        target_key = self.vary_hits_key
                    elif self.src.max_variants_policy == self.src.OBSOLETE_LRU:
                        target_key = self.vary_update_key
                    elif self.src.max_variants_policy == self.src.OBSOLETE_RANDOM:
                        exists_variants = self.con.zrange(self.vary_hits_key, 0, -1)
                        del_keys = random.choices(exists_variants, k=excess)

                    if target_key:
                        try:
                            del_keys = [
                                items[0]
                                for items in self.con.zpopmin(target_key, excess)
                            ]
                        except (ResponseError, *COMMON_ERRORS):
                            # old version of redis or windows not support this command, downgrade
                            for k in self.con.zrange(target_key, 0, -1):
                                if self.con.zrank(target_key, k) < excess:
                                    del_keys.append(k)

                    if del_keys:
                        self.src.clear_variants(*del_keys)

        self.con.zadd(self.hits_key, {k: 0 for k in keys}, nx=True)
        self.con.zadd(self.update_key, {k: last_modified for k in keys})

    def update(self, data: dict, timeout: float = None):
        if self.readonly:
            raise PermissionError(f"Attempt to set val {data} to a readonly cache")
        if timeout == 0:
            # will expire ASAP
            return
        if not data:
            return
        self.prepare(*data)
        dumped = dumps(normalize(data), exclude_types=(int, float), bulk_data=True)
        # for incrby / decrby / incrbyfloat work fine at lua script number typed data will not be dump
        self.con.mset(dumped)

    def set(
        self,
        key: str,
        val,
        timeout: float = None,
        exists_only: bool = False,
        not_exists_only: bool = False,
    ):
        if self.readonly:
            raise PermissionError(
                f"Attempt to set val ({self.keys} -> {repr(val)}) to a readonly cache"
            )
        if timeout == 0:
            # will expire ASAP
            return
        self.prepare(key)
        val = normalize(val)
        dumped = dumps(val, exclude_types=(int, float))
        # for incrby / decrby / incrbyfloat work fine at lua script number typed data will not be dump
        self.con.set(key, dumped, ex=timeout, nx=not_exists_only, xx=exists_only)
