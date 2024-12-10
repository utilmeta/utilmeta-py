from utilmeta.utils import pop, time_now
from typing import Union, Optional, Dict, Any, Tuple
from datetime import datetime
from utype import unprovided
import warnings
import random
from .base import BaseCacheInterface

NUM_TYPES = (int, float)
NUM = Union[int, float]
VAL = Union[str, bytes, list, tuple, dict]

__all__ = ["CacheEntity"]


class CacheEntity:
    backend_name = None

    @property
    def requests_key(self):  # total request keys
        return self.src.encode("requests", "@", self._assigned_variant)
        # cannot perform atomic update sync in common cache backend

    # hit ratio = sum(hits) / total
    @property
    def hits_key(self):
        return self.src.encode("hits", "@", self._assigned_variant)
        # cannot perform atomic update sync in common cache backend

    @property
    def update_key(self):
        # this store every keys (update in set)
        return self.src.encode("update", "@", self._assigned_variant)

    @property
    def vary_hits_key(self):
        return f"{self.src.base_key_prefix}@vary_hits"

    @property
    def vary_update_key(self):
        return f"{self.src.base_key_prefix}@vary_updates"

    def __init__(self, src: "BaseCacheInterface", variant=None, readonly: bool = False):
        assert isinstance(src, BaseCacheInterface)
        self.src = src
        self.readonly = readonly
        self._assigned_variant = variant

    def reset_stats(self):
        self.cache.fetch(
            {
                self.requests_key: 0,
                self.hits_key: {},
            }
        )

    @property
    def variant(self):
        if self._assigned_variant:
            return self._assigned_variant
        return self.src.variant

    @property
    def cache(self):
        return self.src.cache_instance

    # @property
    # def config(self):
    #     return self.src.config

    def get_requests(self):
        return self.cache.get(self.requests_key) or 0

    def get_total_hits(self):
        hits = self.cache.get(self.hits_key) or {}
        return sum(hits.values()) if hits else 0

    def get_key_hits(self, *keys):
        hits = self.cache.get(self.hits_key) or {}
        values = [v for k, v in hits.items() if k in keys]
        return sum(values) if values else 0

    def get_latest_update(self):
        updates = self.cache.get(self.update_key) or {}
        return max(updates.values()) if updates else None

    def _get_key_data(self, vary: bool = False) -> Tuple[dict, dict]:
        tk, uk = (
            (self.vary_hits_key, self.vary_update_key)
            if vary
            else (self.hits_key, self.update_key)
        )
        _data = self.cache.fetch(tk, uk)
        _counts = _data.get(tk)
        _updates = _data.get(uk)
        if not isinstance(_counts, dict):
            _counts = {}
        if not isinstance(_updates, dict):
            _updates = {}
        return _counts, _updates

    def _set_key_data(self, counts: dict, updates: dict, vary: bool = False):
        if not isinstance(counts, dict):
            counts = {}
        if not isinstance(updates, dict):
            updates = {}
        tk, uk = (
            (self.vary_hits_key, self.vary_update_key)
            if vary
            else (self.hits_key, self.update_key)
        )
        self.cache.update({tk: counts, uk: updates})

    @classmethod
    def pop_min(cls, data: dict, count: int):
        reverse_map = {}
        for key, val in data.items():
            if val in reverse_map:
                reverse_map[val].append(key)
            else:
                reverse_map[val] = [key]
        pop_keys = []
        for v in sorted(reverse_map.keys()):
            keys = reverse_map.get(v)
            if not keys:
                continue
            pop_keys.extend(keys)
            if len(pop_keys) > count:
                break
        return pop_keys[:count]

    def prepare(self, *keys: str):
        if not keys:
            return
        if not self.src.trace_keys:
            # not tracing keys behaviours
            return

        last_modified = time_now()
        counts, updates = self._get_key_data()
        # we don't lively trace hit data in set
        # no hit in hits_count means 0 hit
        for k in keys:
            counts.setdefault(k, 0)
        updates.update({k: last_modified for k in keys})

        if self.src.max_entries:
            # counts already set keys
            excess: int = self.exists(*updates) - self.src.max_entries

            if (
                excess > self.src.max_entries_tolerance
            ):  # default to 0, but can set a throttle value
                # total_key >= max_entries
                # delete the least frequently hit key
                del_keys = []
                if self.src.max_entries_policy == self.src.OBSOLETE_LFU:
                    del_keys = self.pop_min(counts, count=excess)
                elif self.src.max_entries_policy == self.src.OBSOLETE_LRU:
                    del_keys = self.pop_min(updates, count=excess)
                elif self.src.max_entries_policy == self.src.OBSOLETE_RANDOM:
                    exists_keys = self.keys()
                    del_keys = random.choices(exists_keys, k=excess)

                if del_keys:
                    self.cache.delete(*keys)
                    # update key metrics
                    for key in del_keys:
                        pop(counts, key)
                        pop(updates, key)

        self._set_key_data(counts, updates)

        if self.variant:
            vary_counts, vary_updates = self._get_key_data(vary=True)
            vary_keys = list(vary_counts)
            vary_counts.setdefault(self.variant, 0)
            vary_updates[self.variant] = last_modified
            self._set_key_data(vary_counts, vary_updates, vary=True)
            # set it here, if it is clearing, the corresponding variant will be deleted
            # in that operation, we do not care about that now

            if self.src.max_variants:
                excess = len(vary_updates) - self.src.max_variants

                if (
                    excess > self.src.max_variants_tolerance
                ):  # default to 0, but can set a throttle value
                    # total_key >= max_entries
                    # delete the least frequently hit key
                    del_keys = []
                    if self.src.max_variants_tolerance == self.src.OBSOLETE_LFU:
                        del_keys = self.pop_min(vary_counts, count=excess)
                    elif self.src.max_variants_policy == self.src.OBSOLETE_LRU:
                        del_keys = self.pop_min(vary_updates, count=excess)
                    elif self.src.max_variants_policy == self.src.OBSOLETE_RANDOM:
                        del_keys = random.choices(vary_keys, k=excess)
                    if del_keys:
                        self.src.clear_variants(*del_keys)

    def update(self, data: Dict[str, Any], timeout: float = unprovided):
        if not data:
            return
        if self.readonly:
            warnings.warn(f"Attempt to set val ({data}) to a readonly cache")
            return
        if timeout == 0:
            # will expire ASAP
            return
        self.prepare(*data)
        self.cache.update(data)
        if not unprovided(timeout):
            self.cache.expire(*data, timeout=timeout)

    def set(
        self,
        key: str,
        val,
        *,
        timeout: float = None,
        exists_only: bool = False,
        not_exists_only: bool = False,
    ):
        if self.readonly:
            warnings.warn(
                f"Attempt to set val ({key} -> {repr(val)}) to a readonly cache, "
                f"(maybe from other scope), ignoring..."
            )
            return
        if timeout == 0:
            # will expire ASAP
            return
        if exists_only:
            if not self.exists(key):
                return
        elif not_exists_only:
            if self.exists(key):
                return
        self.prepare(key)
        self.cache.set(key, val, timeout=timeout)

    def _incr_requests(self, amount=1):
        self.cache.alter(self.requests_key, amount)

    def get(self, *keys: str, single: bool = False):
        if not keys:
            if single:
                return None
            return []

        hits = []
        if single:
            result = self.cache.get(keys[0])
            if result is not None:
                # no hits
                hits = keys
        else:
            result = self.cache.fetch(keys)
            if not result:
                # no hits
                hits = []
            else:
                hits = [k for k in keys if k in result]

        # set key metrics
        if self.src.trace_keys:
            self._incr_requests(len(keys))

            if hits:
                hit_counts = self.cache.get(self.hits_key) or {}
                for key in hits:
                    if key in hit_counts:
                        hit_counts[key] += 1
                    else:
                        hit_counts[key] = 1
                self.cache.set(self.hits_key, hit_counts)

                if self.variant:
                    vary_counts = self.cache.get(self.vary_hits_key) or {}
                    if self.variant in vary_counts:
                        vary_counts[self.variant] += 1
                    else:
                        vary_counts[self.variant] = 1
                    self.cache.set(self.vary_hits_key, vary_counts)

        return result

    def last_modified(self, *keys: str) -> Optional[datetime]:
        if not self.src.trace_keys:
            raise NotImplementedError(
                f"Cache.last_modified not implemented, "
                f"please set trace_keys=True to enable this method"
            )
        updates = self.cache.get(self.update_key)
        if isinstance(updates, dict):
            times = []
            for key in keys:
                dt = updates.get(key)
                if isinstance(dt, datetime):
                    times.append(dt)
            if not times:
                return None
            return max(times)
        return None

    def keys(self):
        if not self.src.trace_keys:
            raise NotImplementedError(
                f"Cache.keys not implemented, "
                f"please set trace_keys=True to enable this method"
            )
        keys = self.cache.get(self.update_key)
        if isinstance(keys, dict):
            misses = []
            exists = []
            for key in keys:
                if key in self.cache:
                    exists.append(key)
                else:
                    misses.append(key)
            if misses:
                # clear the missing data
                counts, updates = self._get_key_data()
                for key in misses:
                    pop(counts, key)
                    pop(updates, key)
                self._set_key_data(counts, updates)
            return exists
        return []

    def clear(self):
        if not self.src.trace_keys:
            raise NotImplementedError(
                f"Cache.clear not implemented, "
                f"please set trace_keys=True to enable this method"
            )
        keys = self.cache.get(self.update_key) or {}
        self.delete(*keys, self.requests_key, self.hits_key, self.update_key)
        if self.variant:
            # clear for this vary
            vary_counts, vary_updates = self._get_key_data(vary=True)
            pop(vary_counts, self.variant)
            pop(vary_updates, self.variant)
            self._set_key_data(vary_counts, vary_updates, vary=True)

    def delete(self, *keys: str):
        if not keys:
            return
        if self.readonly:
            raise RuntimeError(f"Attempt to delete key ({keys}) at a readonly cache")
        self.cache.delete(*keys)
        # update key metrics
        if self.src.trace_keys:
            counts, updates = self._get_key_data()
            for key in keys:
                pop(counts, key)
                pop(updates, key)
            self._set_key_data(counts, updates)

    def expire(self, *keys: str, timeout: float):
        for key in keys:
            self.cache.expire(key, timeout=timeout)

    def count(self) -> int:
        if not self.src.trace_keys:
            raise NotImplementedError(
                f"Cache.count not implemented, "
                f"please set trace_keys=True to enable this method"
            )
        keys = self.cache.get(self.update_key)
        if isinstance(keys, dict):
            # consider timeout
            return self.exists(*keys)
        return 0

    def exists(self, *keys: str) -> int:
        exists = 0
        for key in keys:
            if key in self.cache:
                exists += 1
        return exists

    def variants(self):
        counts = self.cache.get(self.vary_update_key)
        if not counts:
            return []
        return list(counts)  # noqa

    def alter(self, key: str, amount: Union[int, float], limit: int = None):
        # cannot perform atomic limitation, only lua script in redis can do that
        if self.readonly:
            return None
        if not amount:
            return self.get(key, single=True)
        self.prepare(
            key
        )  # still need to prepare, since the command can generate new keys

        if limit is not None:
            value = self.get(key, single=True)
            if isinstance(value, (int, float)):
                if amount > 0:
                    if value + amount > limit:
                        return value
                else:
                    if value + amount < limit:
                        return value
            res = value + amount
            self.cache.set(key, res)
        else:
            self._incr_requests()
            exists = key in self.cache
            if exists:
                res = self.cache.alter(key, delta=amount)
            else:
                res = amount
                self.cache.set(key, amount)

        if limit is None and res is not None:
            # add hits metrics
            if self.src.trace_keys:
                # add hits
                hits = self.cache.get(self.hits_key) or {}
                if key in hits:
                    hits[key] += 1
                else:
                    hits[key] = 1
                self.cache.set(self.hits_key, hits)
                if self.variant:
                    vary_counts = self.cache.get(self.vary_hits_key) or {}
                    if self.variant in vary_counts:
                        vary_counts[self.variant] += 1
                    else:
                        vary_counts[self.variant] = 1
                    self.cache.set(self.vary_hits_key, vary_counts)

        return res

    def lock(self, *keys: str, block: bool = False):
        raise NotImplementedError(f"{self.__class__} not support lock acquire")

    def lpush(self, key: str, *values):
        raise NotImplementedError(f"{self.__class__} not support lpush")

    def rpush(self, key: str, *values):
        raise NotImplementedError(f"{self.__class__} not support rpush")

    def lpop(self, key: str):
        raise NotImplementedError(f"{self.__class__} not support lpop")

    def rpop(self, key: str):
        raise NotImplementedError(f"{self.__class__} not support rpop")
