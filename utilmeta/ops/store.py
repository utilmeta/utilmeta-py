from utype.types import *
import contextvars
from utilmeta.core.response import Response
from utilmeta.core.request import var, Request
from utilmeta.utils import HTTP_METHODS_LOWER
from utilmeta.core.api.specs.openapi import OpenAPISchema
from utilmeta.ops.log.worker import WorkerMetricsLogger
from utilmeta.ops.schema import SupervisorAlertSettingsSchema, SupervisorReportSettingsSchema
from utilmeta.ops.res.metric import BaseMetric
import warnings
if TYPE_CHECKING:
    from utilmeta.ops.models import Resource, Worker, Supervisor, VersionLog
    from utilmeta.ops.alert import AlertEvent, AlertMetric
    from .config import Operations


class OperationsStore(object):
    def __init__(self):
        self.config: Optional["Operations"] = None

        # STORE ==========
        self.worker: Optional["Worker"] = None
        self.server: Optional["Resource"] = None
        self.version: Optional["VersionLog"] = None
        self.supervisor: Optional["Supervisor"] = None
        self.instance: Optional["Resource"] = None
        self.databases: Dict[str, "Resource"] = {}
        self.caches: Dict[str, "Resource"] = {}
        self.openapi: Optional[OpenAPISchema] = None
        self.path_prefix: str = ""

        self.responses_queue: List[Response] = []
        self.endpoints_map: Dict[str, "Resource"] = {}
        self.endpoints_patterns: Dict[Any, Dict[str, str]] = {}

        self.alert_metrics: List["AlertMetric"] = []
        self.alert_events: List["AlertEvent"] = []
        self.report_metrics: List["BaseMetric"] = []

        self.logger = contextvars.ContextVar("_logger")
        self.request_logger = var.RequestContextVar("_logger", cached=True, static=True)
        self.worker_logger = WorkerMetricsLogger()

        self.alert_settings = SupervisorAlertSettingsSchema()
        self.report_settings = SupervisorReportSettingsSchema()

        self._setup = False

    @property
    def ready(self) -> bool:
        return bool(self._setup and self.config)

    @property
    def node_id(self):
        return self.supervisor.node_id if self.supervisor else None

    def setup(self, config: "Operations" = None, close_conn: bool = False):
        from .config import Operations
        self.config = config or Operations.config()

        from utilmeta.ops.models import Resource, Worker
        from utilmeta import service

        self.load_supervisor()
        # reset supervisor

        if not self.server:
            self.server = Resource.get_current_server()
            from utilmeta.ops.task.monitor import get_current_server

            data = get_current_server()
            if not self.server:
                from utilmeta.utils import get_mac_address

                mac = get_mac_address()
                _server = Resource.objects.create(
                    type="server",
                    service=None,
                    # server is a service-neutral resource
                    node_id=self.node_id,
                    ident=mac,
                    data=data,
                    route=f"server/{mac}",
                )
            else:
                if self.server.data != data:
                    self.server.data = data
                    self.server.save(update_fields=["data"])

        if not self.instance:
            self.instance = Resource.get_current_instance()
            from .schema import get_current_instance_data

            data = get_current_instance_data()
            if not self.instance:
                ident = config.address
                self.instance = Resource.objects.create(
                    type="instance",
                    service=service.name,
                    node_id=self.node_id,
                    ident=ident,
                    route=f"instance/{self.node_id}/{ident}" if self.node_id else f"instance/{ident}",
                    server=self.server,
                    data=data,
                )
            else:
                if self.instance.data != data:
                    self.instance.data = data
                    self.instance.save(update_fields=["data"])

        if not self.worker:
            import utilmeta

            if not utilmeta._cmd_env:
                self.worker = Worker.load()

        if not self.endpoints_map:
            endpoints = Resource.filter(
                type="endpoint", service=service.name, deprecated=False
            )

            if self.node_id:
                endpoints = endpoints.filter(node_id=self.node_id)

            self.endpoints_map = {res.ident: res for res in endpoints if res.ident}

        if not self.openapi:
            # path-regex: ident
            self.openapi = config.openapi
            from utilmeta.core.api.specs.openapi import get_operation_id
            from utilmeta.core.api.route import APIRoute

            patterns = {}
            operation_ids = []
            for path, path_item in self.openapi.paths.items():
                if not path_item:
                    continue
                try:
                    pattern = APIRoute.get_pattern(path)
                    methods = {}
                    for method in HTTP_METHODS_LOWER:
                        operation = path_item.get(method)
                        if not operation:
                            continue
                        operation_id = operation.get("operationId")
                        if not operation_id:
                            operation_id = get_operation_id(
                                method, path, excludes=operation_ids, attribute=True
                            )
                        operation_ids.append(operation_id)
                        methods[method] = operation_id
                    if methods:
                        patterns[pattern] = methods
                except Exception as e:
                    warnings.warn(
                        f"generate pattern operation Id at path {path} failed: {e}"
                    )
                    continue

            self.endpoints_patterns = patterns
            if self.openapi.servers:
                url = self.openapi.servers[0].url
                from urllib.parse import urlparse

                self.path_prefix = urlparse(url).path.strip("/")

        if not self.databases:
            from utilmeta.core.orm import DatabaseConnections

            db_config = DatabaseConnections.config()
            dbs = {}
            if db_config and db_config.databases:
                for alias, db in db_config.databases.items():
                    db_obj = Resource.filter(
                        type="database", service=service.name, ident=alias, deprecated=False
                    ).first()
                    if not db_obj:
                        db_obj = Resource.objects.create(
                            type="database",
                            service=service.name,
                            node_id=self.node_id,
                            ident=alias,
                            route=f"database/{self.node_id}/{alias}"
                            if self.node_id else f"database/{alias}",
                            server=self.server if db.local else None,
                        )
                    dbs[alias] = db_obj
                self.databases = dbs

        if not self.caches:
            from utilmeta.core.cache import CacheConnections

            cache_config = CacheConnections.config()
            caches = {}
            if cache_config and cache_config.caches:
                for alias, cache in cache_config.caches.items():
                    if cache.is_memory:
                        # do not monitor memory cache for now
                        continue
                    cache_obj = Resource.filter(
                        type="cache", service=service.name, ident=alias, deprecated=False
                    ).first()
                    if not cache_obj:
                        cache_obj = Resource.objects.create(
                            type="cache",
                            service=service.name,
                            node_id=self.node_id,
                            ident=alias,
                            route=f"cache/{self.node_id}/{alias}" if self.node_id
                            else f"cache/{alias}",
                            server=self.server if cache.local else None,
                        )
                    caches[alias] = cache_obj
                self.caches = caches

        self._setup = True

        if close_conn:
            # close connections
            from django.db import connections
            connections.close_all()

    def load_supervisor(self):
        from utilmeta.ops.models import Supervisor
        from utilmeta.ops.res.metric import BaseMetric
        self.supervisor = Supervisor.current().first()
        if not self.supervisor:
            return

        if self.config.alert:
            try:
                self.alert_settings = SupervisorAlertSettingsSchema(self.supervisor.alert_settings)
            except (TypeError, ValueError):
                pass
            else:
                events = []
                metrics = []

                for item in self.alert_settings.events:
                    evt = self.config.alert.deserialize_event(item)
                    if evt:
                        events.append(evt)

                for item in self.alert_settings.metrics:
                    metric = self.config.alert.deserialize_metric(item)
                    if metric:
                        metrics.append(metric)

                self.alert_events = events
                self.alert_metrics = metrics

        if not self.config.report_disabled:
            try:
                self.report_settings = SupervisorReportSettingsSchema(self.supervisor.report_settings)
            except TypeError:
                pass
            else:
                report_metrics = []
                for metric in self.report_settings.report_metrics:
                    obj = BaseMetric.deserialize(metric.ref)
                    if obj:
                        if metric.kwargs:
                            obj = obj.parametrize(name=metric.name, kwargs=metric.kwargs)
                        report_metrics.append(obj)
                self.report_metrics = report_metrics

    def update_worker(self, **kwargs):
        self.worker_logger.update_worker(
            self.worker, **kwargs
        )

    def get_endpoint_ident(self, request: Request) -> Optional[str]:
        if not self.endpoints_patterns:
            return None
        path = str(request.path or "").strip("/")
        if self.path_prefix:
            if not path.startswith(self.path_prefix):
                return None
            path = path[len(self.path_prefix) :].strip("/")
        for pattern, methods in self.endpoints_patterns.items():
            if pattern.fullmatch(path):
                return methods.get(request.method)
        return None


store = OperationsStore()
