from .base import Config
from utilmeta.utils import TimeZone, get_timezone
from typing import Optional
import time

SERVER_UTCOFFSET = -time.timezone
from datetime import datetime, timezone, timedelta


class Time(Config):
    DATE_DEFAULT = "%Y-%m-%d"
    TIME_DEFAULT = "%H:%M:%S"
    DATETIME_DEFAULT = "%Y-%m-%d %H:%M:%S"

    # ----
    date_format: str = DATE_DEFAULT
    time_format: str = TIME_DEFAULT
    datetime_format: str = DATETIME_DEFAULT
    use_tz: Optional[bool] = None
    time_zone: Optional[str] = None

    def __init__(
        self,
        *,
        date_format: str = DATE_DEFAULT,
        time_format: str = TIME_DEFAULT,
        datetime_format: str = DATETIME_DEFAULT,
        # to_timestamp: bool = False,
        # to_ms_timestamp: bool = False,
        use_tz: Optional[bool] = True,
        time_zone: Optional[str] = None,
    ):
        super().__init__(locals())
        self.time_format = time_format
        self.date_format = date_format
        self.datetime_format = datetime_format
        self.time_zone = time_zone
        self.use_tz = use_tz

    def hook(self, service):
        self.register_encoders()
        # used in service

    def register_encoders(self):
        from utype import register_encoder
        from datetime import date, datetime, time

        @register_encoder(date, allow_subclasses=False)
        def from_date(data: date):
            if self.date_format:
                return data.strftime(self.date_format)
            return data.isoformat()

        @register_encoder(time)
        def from_time(data: time):
            if self.time_format:
                return data.strftime(self.time_format)
            r = data.isoformat()
            if data.microsecond:
                r = r[:12]
            return r

        @register_encoder(datetime)
        def from_dt(data: datetime):
            if self.datetime_format:
                return data.strftime(self.datetime_format)
            return data.isoformat()

    @property
    def use_utc_ts(self):
        if self.use_tz:
            return True
        if self.time_zone == TimeZone.UTC:
            return True
        return False

    @property
    def server_utcoffset(self) -> int:
        # django might change the timezone in Unix systems
        # so record SERVER_UTCOFFSET before configure django
        return SERVER_UTCOFFSET

    @property
    def timezone(self):
        return get_timezone(self.time_zone) if self.time_zone else None

    @property
    def timezone_utcoffset(self) -> int:
        if not self.time_zone:
            return self.server_utcoffset
        return int(datetime.now(self.timezone).utcoffset().total_seconds())

    @property
    def value_utcoffset(self) -> int:
        if self.use_tz:
            return 0
        return self.timezone_utcoffset

    def time_local(self, dt: datetime = None):
        dt = dt or datetime.now()
        return dt.astimezone(self.timezone).replace(tzinfo=None)

    def time_now(self, relative: datetime = None) -> datetime:
        local_now = self.time_local()
        if relative:
            if relative.tzinfo:
                return datetime.utcnow().replace(tzinfo=timezone.utc)
            return local_now
        if self.use_tz:
            return datetime.utcnow().replace(tzinfo=timezone.utc)
        return local_now

    def convert_time(self, dt: datetime) -> datetime:
        if self.use_tz:
            if not dt.tzinfo:
                return dt.astimezone(tz=timezone.utc)
            return dt
        if dt.tzinfo:
            return self.time_local(dt)
        if self.timezone_utcoffset != self.server_utcoffset:
            return dt + timedelta(
                seconds=self.timezone_utcoffset - self.server_utcoffset
            )
        return dt
