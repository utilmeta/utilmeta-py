from utilmeta.core.response import Response
from utilmeta.core.request import var, Request
from utilmeta.utils.context import ContextProperty, Property
from typing import List, Optional, Union
from utilmeta.core.server import ServiceMiddleware
from utilmeta.utils import file_like, SECRET, Header, HTTPMethod, normalize, time_now, Error
from .config import Operations
import threading
import contextvars
from datetime import timedelta
import os
import time
from functools import wraps


_responses_queue: List[Response] = []
_endpoints_map: dict = {}
_worker = None
_server = None
_version = None
_supervisor = None
_instance = None
_logger = contextvars.ContextVar('_logger')

request_logger = var.RequestContextVar('_logger', cached=True, static=True)


class LogLevel:
    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3


LOG_LEVELS = ['DEBUG', 'INFO', 'WARN', 'ERROR']


def level_log(f):
    lv = f.__name__.upper()
    if lv not in LOG_LEVELS:
        raise ValueError(f'Invalid log level: {lv}')
    index = LOG_LEVELS.index(lv)

    @wraps(f)
    def emit(self: 'Logger', brief: str, msg: str = None, **kwargs):
        return self.emit(brief, level=index, data=kwargs, msg=msg)
    return emit


def setup_locals(config: Operations):
    from .models import VersionLog, Resource, Worker, Supervisor
    from utilmeta import service

    global _worker, _version, _supervisor, _instance, _server, _endpoints_map
    if not _server:
        _server = Resource.get_current_server()
    if not _instance:
        _instance = Resource.get_current_instance()
    if not _worker:
        _worker = Worker.get(os.getpid())
    if not _supervisor:
        _supervisor = Supervisor.objects.filter(
            service=service.name,
            ops_api=config.ops_api,
            disabled=False
        ).first()
    if not _version:
        if _instance:
            _version = VersionLog.objects.create(
                instance=_instance,
                version=service.version_str,
                service=service.name,
                node_id=_supervisor.node_id if _supervisor else None,
            )
    if not _endpoints_map:
        _endpoints = Resource.objects.filter(
            type='endpoint',
            service=service.name,
            deleted=False,
            deprecated=False
        )

        if _supervisor:
            _endpoints = _endpoints.filter(node_id=_supervisor.node_id)

        _endpoints_map = {res.ident: res for res in _endpoints}

    # close connections
    from django.db import connections
    connections.close_all()


class LogMiddleware(ServiceMiddleware):
    def __init__(self, config: Operations):
        super().__init__(config=config)
        self.config = config

    def process_request(self, request: Request):
        # log = request_logger.setup(request)
        # log.set(Logger())   # set logger
        logger = self.config.logger_cls()
        _logger.set(logger)
        request_logger.setter(request, logger)

    def process_response(self, response: Response):
        logger = _logger.get(None)
        if not logger:
            return
        if not response.request:
            return

        logger.exit()

        if logger.omitted:
            return

        global _responses_queue
        _responses_queue.append(response)

        if len(_responses_queue) >= self.config.max_backlog:
            threading.Thread(
                target=batch_save_logs,
                kwargs=dict(
                    close=True
                )
            ).start()


class Logger(Property):
    __context__ = ContextProperty(_logger)

    middleware_cls = LogMiddleware

    DEFAULT_VOLATILE = True
    EXCLUDED_METHODS = (HTTPMethod.OPTIONS, HTTPMethod.CONNECT, HTTPMethod.TRACE, HTTPMethod.HEAD)
    VIOLATE_MAINTAIN: timedelta = timedelta(days=1)
    MAINTAIN: timedelta = timedelta(days=30)        # ALL LOGS
    PERSIST_DURATION = timedelta(seconds=1)
    PERSIST_LEVEL = LogLevel.WARN
    STORE_DATA_LEVEL = LogLevel.WARN
    STORE_RESULT_LEVEL = LogLevel.WARN
    STORE_HEADERS_LEVEL = LogLevel.WARN

    def __init__(self,
                 from_logger: 'Logger' = None,
                 span_data: dict = None
                 ):
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
        
        self._from_logger = from_logger
        self._span_logger: Optional[Logger] = None
        self._span_data = span_data
        self._client_responses = []
        self._events = []
        self._messages = []
        self._briefs = []
        self._level = None
        self._omitted = False
        self._exited = False
        self._volatile = self.DEFAULT_VOLATILE

    def relative_time(self, to=None):
        return max(int(((to or time.time()) - self.init_time) * 1000), 0)

    @property
    def from_logger(self):
        return self._from_logger

    @property
    def omitted(self):
        return self._omitted

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
        assert name, f'Empty scope name'
        self._span_data = dict(
            name=name,
            **kwargs
        )
        return self

    def __enter__(self) -> 'Logger':
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
        _logger.set(logger)
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

    def generate_request_logs(self, context_type='service_log', context_id=None):
        if not self._client_responses:
            return []

        objects = []

        for resp in self._client_responses:
            log = self.generate_request_log(
                resp,
                context_type=context_type,
                context_id=context_id
            )
            if log:
                objects.append(log)
        return objects

    def generate_request_log(self, response: Response,
                             context_type='service_log',
                             context_id=None):
        from .models import RequestLog
        return RequestLog(

        )

    @classmethod
    def get_out_traffic(cls, response: Response) -> int:
        if not response:
            return 0
        length = response.content_length
        for key, val in response.headers.items():
            length += len(key) + len(val)
        return length

    def parse_values(self, data):
        if not self.config.secret_names:
            return data
        if data is None:
            return data
        if isinstance(data, dict):
            result = {}
            for k, v in data.items():
                k: str
                if isinstance(v, list):
                    result[k] = self.parse_values(v)
                elif file_like(v):
                    result[k] = str(v)
                else:
                    for key in self.config.secret_names:
                        if key in k.lower():
                            v = SECRET
                            break
                    result[k] = v
            return result
        if isinstance(data, list):
            result = []
            for d in data:
                if file_like(d):
                    result.append(str(d))
                else:
                    result.append(d)
            return result
        if file_like(data):
            return None
        return str(data)

    def generate_log(self, response: Response):
        from utilmeta.ops.models import ServiceLog
        from .api import access_token_var

        request = response.request
        duration = response.duration_ms
        # resp_length = response_length(response, content_only=True)
        # resp_full_length = response_length(response, content_only=False)
        # req_full_length = request_length(request)
        status = response.status
        path = request.path
        # in_traffic = req_full_length
        # out_traffic = resp_full_length
        level = self.level
        if level is None:
            level = self.status_level(status)
        method = request.method.lower()
        user_id = var.user_id.getter(request)
        query = self.parse_values(request.query or {})
        data = None
        result = None

        if level >= self.STORE_DATA_LEVEL:
            # if data should be saved
            data = self.parse_values(var.data.getter(request))

        if level >= self.STORE_RESULT_LEVEL:
            result = response.data
            if file_like(result):
                result = '<file>'

        try:
            public = request.ip_address.is_global
        except ValueError:
            public = False

        volatile = self.volatile
        if level >= self.PERSIST_LEVEL:
            volatile = False
        if duration and duration >= self.PERSIST_DURATION.total_seconds() * 1000:
            volatile = False

        request_headers = {}
        response_headers = {}
        if level >= self.STORE_HEADERS_LEVEL:
            request_headers = self.parse_values(dict(request.headers))
            response_headers = self.parse_values(dict(response.headers))

        operation_names = var.operation_names.getter(request) or []
        endpoint_ident = '_'.join(operation_names)
        endpoint_ref = var.endpoint_ref.getter(request) or None
        endpoint = _endpoints_map.get(endpoint_ident) if endpoint_ident else None
        access_token = access_token_var.getter(request)

        try:
            level_str = LOG_LEVELS[level]
        except IndexError:
            level_str = LogLevel.DEBUG

        return ServiceLog(
            service=self.service.name,
            instance=_instance,
            version=_version,
            node_id=getattr(_supervisor, 'node_id', None),
            supervisor=_supervisor,
            access_token_id=getattr(access_token, 'id', None),
            level=level_str,
            volatile=volatile,
            time=request.time,
            duration=duration,
            worker=_worker,
            scheme=request.scheme,
            thread_id=self.current_thread,
            public=public,
            path=path,
            full_url=request.url,
            query=query,
            data=data,
            result=result,
            user_id=user_id,
            ip=str(request.ip_address),
            status=status,
            request_type=request.content_type,
            response_type=response.content_type,
            request_headers=request_headers,
            response_headers=response_headers,
            length=response.content_length,
            method=method,
            endpoint=endpoint,
            endpoint_ident=endpoint_ident,
            endpoint_ref=endpoint_ref,
            messages=self.messages,
            trace=self.get_trace(),
        )

    def get_trace(self):
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

            _logger.set(self.from_logger)
        else:
            _logger.set(None)

    def emit(self, brief: str, level: int, data: dict, msg: str = None):
        if isinstance(brief, Exception):
            brief = Error(brief)
        if isinstance(brief, Error):
            msg = brief.message
            brief = str(brief)

        if self._span_logger:
            return self._span_logger.emit(brief, level, data, msg=msg)
        if self._level < level:
            self._level = level
        name = LOG_LEVELS[level]
        self._events.append(dict(
            name=name,
            init=self.relative_time(),
            type=f'log.{name.lower()}',
            msg=self._push_message(brief, msg=msg),
            data=data,
        ))

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
        return '\n'.join(self._messages)

    @property
    def brief_message(self) -> str:
        return '; '.join(self._briefs)


def batch_save_logs(close: bool = False):
    from utilmeta.ops.models import ServiceLog, QueryLog, RequestLog, Resource, Worker

    with threading.Lock():
        global _responses_queue
        queue = _responses_queue
        _responses_queue = []
        # ----------------
        logs_creates = []
        logs_updates = []
        query_logs = []
        request_logs = []

        for response in queue:
            response: Response
            try:
                logger: Logger = request_logger.getter(response.request)
                if not logger:
                    continue

                service_log = logger.generate_log(
                    response
                )

                if not service_log:
                    continue

                if service_log.id:
                    logs_updates.append(service_log)
                else:
                    logs_creates.append(service_log)
            finally:
                response.close()

        if not logs_creates and not logs_updates:
            return

        if logs_updates:
            for log in logs_updates:
                log.save()

        if logs_creates:
            ServiceLog.objects.bulk_create(logs_creates, ignore_conflicts=True)

        if query_logs:
            QueryLog.objects.bulk_create(query_logs, ignore_conflicts=True)

        if request_logs:
            RequestLog.objects.bulk_create(request_logs, ignore_conflicts=True)

    if close:
        from django.db import connections
        connections.close_all()

    return


def omit_log():
    pass
