import warnings

from utilmeta.core.response import Response
from utilmeta.core.request import var, Request
from utilmeta.utils.context import ContextProperty, Property
from typing import Optional, Union
from utilmeta.utils import (
    HAS_BODY_METHODS,
    hide_secret_values,
    normalize,
    Error,
    parse_user_agents,
)
from utilmeta.ops.config import Operations
import threading
import time
from functools import wraps
from utilmeta.ops.store import store


class LogLevel:
    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3


LOG_LEVELS = ["DEBUG", "INFO", "WARN", "ERROR"]


def level_log(f):
    lv = f.__name__.upper()
    if lv not in LOG_LEVELS:
        raise ValueError(f"Invalid log level: {lv}")
    index = LOG_LEVELS.index(lv)

    @wraps(f)
    def emit(self: "Logger", brief: str, msg: str = None, **kwargs):
        return self.emit(brief, level=index, data=kwargs, msg=msg)

    return emit


class Logger(Property):
    __context__ = ContextProperty(store.logger)

    def __init__(self, from_logger: "Logger" = None, span_data: dict = None):
        super().__init__()
        from utilmeta import service

        self.service = service
        self.config = service.get_config(Operations)
        self.current_thread = threading.current_thread().ident
        self.init_time = time.time()
        if from_logger:
            self.init_time = from_logger.init_time
        self.init = self.relative_time()
        self.duration = None

        self._request = None
        self._supervised = False
        self._from_logger = from_logger
        self._span_logger: Optional[Logger] = None
        self._span_data = span_data
        self._client_responses = []
        self._events = []
        self._messages = []
        self._briefs = []
        self._exceptions = []
        self._level = None
        self._omitted = False
        self._events_only = False
        self._server_timing = False
        self._exited = False
        self._volatile = self.config.log.default_volatile
        self._store_data_level = self.config.log.store_data_level
        self._store_result_level = self.config.log.store_result_level
        self._store_headers_level = self.config.log.store_headers_level
        self._persist_level = self.config.log.persist_level
        self._persist_duration_limit = self.config.log.persist_duration_limit
        if self._store_data_level is None:
            self._store_data_level = (
                LogLevel.WARN if service.production else LogLevel.INFO
            )
        if self._store_headers_level is None:
            self._store_headers_level = (
                LogLevel.WARN if service.production else LogLevel.INFO
            )
        if self._store_result_level is None:
            self._store_result_level = (
                LogLevel.WARN if service.production else LogLevel.INFO
            )

    def relative_time(self, to=None):
        return max(int(((to or time.time()) - self.init_time) * 1000), 0)

    @property
    def from_logger(self):
        return self._from_logger

    @property
    def omitted(self):
        return self._omitted

    @property
    def events_only(self):
        return self._events_only

    @property
    def vacuum(self):
        return (
            not self._messages
            and not self._events
            and not self._exceptions
            and not self._span_logger
        )

    @property
    def level(self):
        return self._level

    @property
    def messages(self):
        return self._messages

    @property
    def volatile(self):
        return self._volatile

    @volatile.setter
    def volatile(self, v):
        self._volatile = v

    @classmethod
    def status_level(cls, status: int):
        level = LogLevel.INFO
        if not status:
            level = LogLevel.ERROR
        elif status >= 500:
            level = LogLevel.ERROR
        elif status >= 400:
            level = LogLevel.WARN
        return level

    def __call__(self, name: str, **kwargs):
        if self._span_logger:
            return self._span_logger(name, **kwargs)
        assert name, f"Empty scope name"
        self._span_data = dict(name=name, **kwargs)
        return self

    def __enter__(self) -> "Logger":
        if self._span_logger:
            return self._span_logger.__enter__()
        if not self._span_data:
            return self
        data = dict(self._span_data)
        self._events.append(data)
        logger = Logger(
            span_data=data,
            from_logger=self,
        )
        logger._request = self._request
        logger._supervised = self._supervised
        logger._server_timing = self._server_timing
        store.logger.set(logger)
        self._span_logger = logger
        return logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._span_logger:
            return
        self._span_logger: Logger
        self._span_logger.exit()
        # self._events.append(self._span_logger.span)
        if self._span_data:
            # update
            self._span_data.update(self._span_logger.span)
        self._span_logger = None

    @property
    def span(self):
        data = dict(
            init=self.init,
            time=self.duration,
            events=self._events,
        )
        # if self._queries_num:
        #     data.update(
        #         queries=self._queries_num,
        #         queries_time=self._queries_duration,
        #     )
        # if self._outbound_requests_num:
        #     data.update(
        #         outbound_requests=self._outbound_requests_num,
        #         outbound_requests_time=self._outbound_duration,
        #     )
        return data

    def setup_request(self, request: Request):
        self._request = request
        if store.supervisor:
            supervisor_id = request.headers.get(
                "x-utilmeta-node-id"
            ) or request.headers.get("x-node-id")
            supervisor_hash = request.headers.get("X-utilmeta-supervisor-key-md5")
            if supervisor_hash and supervisor_id == store.supervisor.node_id:  # noqa
                import hashlib

                if hashlib.md5(_supervisor.public_key) == supervisor_hash:  # noqa
                    self._supervised = True
        if self._supervised:
            log_options = request.headers.get("x-utilmeta-log-options")
            if log_options:
                options = [
                    option.strip() for option in str(log_options).lower().split(",")
                ]
                if "omit" in options:
                    self._omitted = True
                if "timing" in options or "server-timing" in options:
                    self._server_timing = True

    def omit(self, val: bool = True):
        self._omitted = val

    def make_events_only(self, val: bool = True):
        self._events_only = val

    def setup_response(self, response: Response):
        if self._supervised:
            if self._server_timing:
                duration = response.duration_ms or self.duration
                ts = (
                    response.request.time.timestamp()
                    if response.request
                    else self.init_time
                )
                if duration:
                    response.set_header(
                        "Server-Timing", f"total;dur={duration};ts={ts}"
                    )

    def generate_request_logs(self, context_type="service_log", context_id=None):
        if not self._client_responses:
            return []

        objects = []

        for resp in self._client_responses:
            log = self.generate_request_log(
                resp, context_type=context_type, context_id=context_id
            )
            if log:
                objects.append(log)
        return objects

    def generate_request_log(
        self, response: Response, context_type="service_log", context_id=None
    ):
        from utilmeta.ops.models import RequestLog
        from utilmeta.ops.alert.event import event

        request = response.request
        status = response.status
        request_headers = {}
        response_headers = {}
        level = None
        data = None
        result = None
        if level is None:
            level = self.status_level(response.status)
        if level >= self._store_headers_level:
            request_headers = self.parse_values(dict(request.headers))
            response_headers = self.parse_values(
                dict(response.prepare_headers(with_content_type=True))
            )

        if level >= self._store_data_level:
            if request.method in HAS_BODY_METHODS:
                # if data should be saved
                try:
                    data = self.parse_values(request.data)
                except Exception as e:  # noqa: ignore
                    warnings.warn(f"load request data failed: {e}")

        if level >= self._store_result_level:
            try:
                result = self.parse_values(response.data)
            except Exception as e:  # noqa: ignore
                warnings.warn(f"load response data failed: {e}")

        # ALERT -----
        alert_event = None
        alert_log = None

        if not status or response.is_timeout:
            alert_event = event.api_timeout_outbound_request
        elif status >= 400:
            alert_event = event.api_error_outbound_request
        if alert_event:
            alert_log = alert_event(
                None, response.time,
                method=request.method,
                url=request.url,
                status=status,
            )
        # ----------

        return RequestLog(
            service=self.service.name,
            time=request.time,
            duration=response.duration_ms,
            node_id=store.node_id,
            context_type=context_type,
            context_id=context_id,
            instance=store.instance,
            worker=store.worker,
            host=request.host,
            asynchronous=request.adaptor.get_context("asynchronous"),
            timeout=request.adaptor.get_context("timeout"),
            timeout_error=response.is_timeout,
            server_error=response.is_server_error,
            client_error=response.is_client_error,
            alert=alert_log,
            # --
            scheme=request.scheme,
            in_traffic=response.traffic,
            out_traffic=request.traffic,
            path=request.path,
            full_url=request.url,
            query=request.query,
            data=data,
            result=result,
            user_agent=parse_user_agents(request.headers.get("user-agent")),
            status=status,
            request_type=str(request.content_type)[:200] if request.content_type else None,
            response_type=str(response.content_type)[:200] if response.content_type else None,
            request_headers=request_headers,
            response_headers=response_headers,
            length=response.content_length,
            method=request.method,
        )

    @classmethod
    def get_file_repr(cls, file):
        return "<file>"

    def parse_values(self, data):
        return hide_secret_values(
            data, secret_names=self.config.secret_names, file_repr=self.get_file_repr
        )

    def generate_log(self, response: Response):
        from utilmeta.ops.models import ServiceLog
        from utilmeta.ops.api import access_token_var
        from utilmeta.ops.alert.event import event

        request = response.request
        duration = response.duration_ms

        status = response.status
        path = request.path
        in_traffic = request.traffic
        out_traffic = response.traffic
        level = self.level
        if level is None:
            level = self.status_level(status)

        if response.error:
            self.commit_error(response.error)

        method = str(request.adaptor.request_method).lower()
        user_id = var.user_id.getter(request, default=None)
        query = self.parse_values(request.query or {})
        data = None
        result = None

        if level >= self._store_data_level:
            if method in HAS_BODY_METHODS:
                # if data should be saved
                try:
                    data = self.parse_values(request.data)
                except Exception as e:  # noqa: ignore
                    warnings.warn(f"load request data failed: {e}")

        if level >= self._store_result_level:
            try:
                result = self.parse_values(response.data)
            except Exception as e:  # noqa: ignore
                warnings.warn(f"load response data failed: {e}")

        try:
            public = request.ip_address.is_global
        except ValueError:
            public = False

        volatile = self.volatile
        if level >= self._persist_level:
            volatile = False
        if self._persist_duration_limit:
            if duration and duration >= self._persist_duration_limit * 1000:
                volatile = False

        request_headers = {}
        response_headers = {}
        if level >= self._store_headers_level:
            request_headers = self.parse_values(dict(request.headers))
            response_headers = self.parse_values(
                dict(response.prepare_headers(with_content_type=True))
            )

        operation_names = var.operation_names.getter(request)
        if operation_names:
            endpoint_ident = "_".join(operation_names)
        else:
            # or find it by the generated openapi items (match method and path, find operationId)
            endpoint_ident = store.get_endpoint_ident(request)

        endpoint_ref = var.endpoint_ref.getter(request) or None
        endpoint = store.endpoints_map.get(endpoint_ident) if endpoint_ident else None
        access_token = access_token_var.getter(request)

        try:
            level_str = LOG_LEVELS[level]
        except IndexError:
            level_str = LogLevel.DEBUG

        # ALERT -----
        alert_event = None
        alert_log = None
        if status >= 500:
            alert_event = event.api_5xx_response
        elif status >= 400:
            alert_event = event.api_4xx_response

        if alert_event:
            alert_log = alert_event(
                endpoint_ident, request.time,
                method=method,
                url=request.url,
                status=status,
                result=result,
                user_id=user_id,
                brief_message=self.brief_message,
            )
        # -----------

        return ServiceLog(
            service=self.service.name,
            instance=store.instance,
            version=store.version,
            node_id=store.node_id,
            supervisor=store.supervisor,
            access_token_id=getattr(access_token, "id", None),
            level=level_str,
            volatile=volatile,
            time=request.time,
            duration=duration,
            worker=store.worker,
            thread_id=self.current_thread,
            alert=alert_log,
            # --- Web mixin
            scheme=request.scheme,
            in_traffic=in_traffic,
            out_traffic=out_traffic,
            public=public,
            path=path,
            full_url=request.url,
            query=query,
            data=data,
            result=result,
            user_agent=parse_user_agents(request.headers.get("user-agent")),
            status=status,
            request_type=str(request.content_type)[:200] if request.content_type else None,
            response_type=str(response.content_type)[:200] if response.content_type else None,
            request_headers=request_headers,
            response_headers=response_headers,
            length=response.content_length,
            method=method,
            # --
            user_id=str(user_id) if user_id else None,
            ip=str(request.ip_address),
            endpoint=endpoint,
            endpoint_ident=str(endpoint_ident)[:500] if endpoint_ident else None,
            endpoint_ref=str(endpoint_ref)[:500] if endpoint_ref else None,
            messages=self.messages,
            trace=self.get_trace(),
        )

    def get_trace(self):
        self._events.sort(key=lambda v: v.get("init", 0))
        return normalize(self._events, _json=True)

    def exit(self):
        if self._exited:
            return
        self._exited = True
        if self.duration is None:
            # forbid to recalculate
            self.duration = self.relative_time() - self.init

        if self._span_logger:
            self._span_logger.exit()

        if self.from_logger:
            if self._span_data:
                self._span_data.update(self.span)

            store.logger.set(self.from_logger)
        else:
            store.logger.set(None)

    def emit(
        self, brief: Union[str, Error], level: int, data: dict = None, msg: str = None
    ):
        if self._span_logger:
            return self._span_logger.emit(brief, level, data, msg=msg)

        exception = None
        ts = None
        if isinstance(brief, Exception):
            exception = brief
            brief = Error(brief)

        if isinstance(brief, Error):
            brief.setup()
            ts = brief.ts
            exception = brief.exception
            msg = brief.message
            brief = str(brief)

        if not level:
            level = LogLevel.INFO

        if self._level is None:
            self._level = level
        else:
            if self._level < level:
                self._level = level

        if exception:
            self._exceptions.append(exception)

        name = LOG_LEVELS[level]
        self._events.append(
            dict(
                name=name,
                init=self.relative_time(ts),
                type=f"log.{name.lower()}",
                msg=self._push_message(brief, msg=msg),
                data=data,
            )
        )

    def commit_error(self, e: Error):
        if e.exception in self._exceptions:
            return
        self._exceptions.append(e.exception)
        level = self.status_level(e.status)
        self.emit(e, level=level)

    def _push_message(self, brief: str, msg: str = None):
        brief = str(brief)
        msg = str(msg or brief)
        if not msg:
            return None
        if self.from_logger:
            return self.from_logger._push_message(brief, msg)
        if brief not in self._briefs:
            self._briefs.append(brief)
        if msg not in self._messages:
            self._messages.append(msg)
        return self._messages.index(msg)

    @level_log
    def debug(self, brief: Union[str, Exception], msg: str = None, **kwargs):
        pass

    @level_log
    def info(self, brief: Union[str, Exception], msg: str = None, **kwargs):
        pass

    @level_log
    def warn(self, brief: Union[str, Exception], msg: str = None, **kwargs):
        pass

    @level_log
    def error(self, brief: Union[str, Exception], msg: str = None, **kwargs):
        pass

    @property
    def message(self) -> str:
        return "\n".join(self._messages)

    @property
    def brief_message(self) -> str:
        return "; ".join(self._briefs)


# def omit_log():
#     pass
