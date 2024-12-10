from datetime import datetime, timedelta, tzinfo, timezone
from typing import Union, Optional
import decimal

__all__ = [
    "closest_hour",
    "local_time_offset",
    "get_interval",
    "time_now",
    "time_local",
    "convert_time",
    "utc_ms_ts",
    "wait_till",
    "get_timezone",
]


def utc_ms_ts() -> int:
    return int(datetime.now().timestamp() * 1000)


def get_timezone(timezone_name: str) -> tzinfo:
    if timezone_name.lower() == "utc":
        return timezone.utc
    try:
        import zoneinfo

        return zoneinfo.ZoneInfo(timezone_name)
    except ModuleNotFoundError:
        try:
            from backports import zoneinfo

            return zoneinfo.ZoneInfo(timezone_name)
            # django > 4.0
        except ModuleNotFoundError:
            try:
                import pytz  # noqa

                return pytz.timezone(timezone_name)
            except ModuleNotFoundError:
                raise ModuleNotFoundError(
                    "You should install zoneinfo or pytz to use timezone feature"
                )


def wait_till(ts: Union[int, float, datetime], tick: float = None):
    import time

    if isinstance(ts, datetime):
        ts = ts.timestamp()
    if tick is None:
        delta = max(0.0, ts - time.time())
        if delta:
            time.sleep(delta)
        return
    while True:
        delta = max(0.0, ts - time.time())
        if not delta:
            return
        if delta < tick:
            time.sleep(delta)
            return
        else:
            time.sleep(tick)


def time_now(relative: datetime = None) -> datetime:
    from utilmeta.conf.time import Time

    return (Time.config() or Time()).time_now(relative)


def time_local(dt: datetime = None) -> datetime:
    from utilmeta.conf.time import Time

    return (Time.config() or Time()).time_local(dt)


def convert_time(dt: datetime) -> datetime:
    from utilmeta.conf.time import Time

    return (Time.config() or Time()).convert_time(dt)


def get_interval(
    interval: Union[int, float, decimal.Decimal, timedelta],
    null: bool = False,
    ge: Optional[Union[int, float, decimal.Decimal, timedelta]] = 0,
    silent: bool = False,
    le: Optional[Union[int, float, decimal.Decimal, timedelta]] = None,
) -> Optional[float]:
    if interval is None:
        if null:
            return interval
        raise TypeError(f"interval is not null")
    if isinstance(interval, (int, float, decimal.Decimal)):
        interval = float(interval)
    elif isinstance(interval, timedelta):
        interval = interval.total_seconds()
    else:
        if silent:
            return 0
        raise TypeError(
            f"Invalid interval: {interval}, must be int, float or timedelta object"
        )
    if ge is not None:
        if not isinstance(ge, (int, float)):
            ge = get_interval(ge)
        if interval < ge:
            if silent:
                return ge
            raise ValueError(f"Invalid interval: {interval}, must greater than {ge}")
    if le is not None:
        if not isinstance(le, (int, float)):
            le = get_interval(le)
        if interval > le:
            if silent:
                return le
            raise ValueError(f"Invalid interval: {interval}, must less than {le}")
    return interval


def local_time_offset(t=None):
    """Return offset of local zone from GMT, either at present or at time t."""
    import time

    if t is None:
        t = time.time()
    if time.localtime(t).tm_isdst and time.daylight:
        return -time.altzone
    else:
        return -time.timezone


def closest_hour(dt: datetime) -> datetime:
    lo = datetime(
        year=dt.year, month=dt.month, day=dt.day, hour=dt.hour, tzinfo=dt.tzinfo
    )
    hi = datetime(
        year=dt.year, month=dt.month, day=dt.day, hour=dt.hour, tzinfo=dt.tzinfo
    ) + timedelta(hours=1)
    if dt - lo > hi - dt:
        return hi
    return lo
