from utype.types import *
import os
import psutil
from django.db import models
from utilmeta.utils import (time_now, get_sys_net_connections_info,
                            get_system_fds, cached_function, Error)
from typing import TYPE_CHECKING, Optional
from utilmeta.ops.schema import AlertSettingsParams
from utilmeta.ops.res.metric import MetricType, ValueType, AggregationType, BaseMetricRegistry, BaseMetric
from .config import Alert
from utilmeta.ops.store import store
from .event import event

if TYPE_CHECKING:
    from utilmeta.ops.models import ServerMonitor, InstanceMonitor, DatabaseMonitor, CacheMonitor, Resource
    from utilmeta.ops.query import DatabaseFullMetrics, CacheFullMetrics

from .utils import ResourceType


def alert_metric(
    resource_type: str,
    metric_type: str = None,
    value_type: str = None,
    default_category: str = None,
    aggregation_type: str = None,
    unit: str = None,
    title: str = '',
    description: str = '',
    max_value: float = None,
    min_value: float = None,
    default_threshold: float = None,
    default_exceed: bool = None,
):
    def wrapper(f):
        return BaseMetric(
            f,
            resource_type=resource_type,
            title=title,
            description=description,
            max_value=max_value,
            min_value=min_value,
            default_threshold=default_threshold,
            default_exceed=default_exceed,
            default_category=default_category,
            metric_type=metric_type,
            value_type=value_type,
            value_unit=unit,
            aggregation_type=aggregation_type,
        )
    return wrapper


class AlertMetricRegistry(BaseMetricRegistry):
    @classmethod
    def get_current_instance(cls) -> Optional["Resource"]:
        from utilmeta.ops.models import Resource
        return Resource.get_current_instance()

    @classmethod
    def get_current_server(cls) -> Optional["Resource"]:
        from utilmeta.ops.models import Resource
        return Resource.get_current_server()

    @classmethod
    def get_current_logs(cls, endpoint: str = None) -> models.QuerySet:
        from utilmeta.ops.models import ServiceLog
        logs = ServiceLog.get_current_logs()
        if endpoint:
            logs = logs.filter(
                models.Q(
                    endpoint_id=endpoint
                ) | models.Q(
                    endpoint__ident=endpoint
                ) | models.Q(
                    endpoint__remote_id=endpoint
                ) | models.Q(
                    endpoint__ident=endpoint
                ) | models.Q(
                    endpoint__ref=endpoint
                )
            )
        return logs

    @classmethod
    def get_databases(cls) -> models.QuerySet:
        from utilmeta.ops.models import Resource
        return Resource.get_current_databases()

    @classmethod
    def get_caches(cls) -> models.QuerySet:
        from utilmeta.ops.models import Resource
        return Resource.get_current_caches()

    @classmethod
    def get_workers(cls) -> models.QuerySet:
        from utilmeta.ops.models import Worker
        return Worker.current_workers()

    # cached in this cycle
    @cached_function
    def get_current_instance_metrics(self) -> Optional["InstanceMonitor"]:
        from utilmeta.ops.models import InstanceMonitor
        config = Alert.config()
        return InstanceMonitor.objects.filter(
            instance=self.get_current_instance(),
            layer=0,
            time__gte=time_now() - timedelta(seconds=config.current_monitor_time_limit)
        ).order_by('time').last()

    @cached_function
    def get_current_server_metrics(self) -> Optional["ServerMonitor"]:
        from utilmeta.ops.models import ServerMonitor
        config = Alert.config()
        return ServerMonitor.objects.filter(
            server=self.get_current_server(),
            layer=0,
            time__gte=time_now() - timedelta(seconds=config.current_monitor_time_limit)
        ).order_by('time').last()

    @cached_function
    def get_database_metrics(self, alias: str) -> Optional["DatabaseFullMetrics"]:
        from utilmeta.ops.models import DatabaseMonitor, Resource
        from utilmeta.ops.query import DatabaseFullMetrics

        db: Resource = self.get_databases().filter(
            models.Q(ident=alias) | models.Q(remote_id=alias)
        ).first()
        if not db:
            return None
        config = Alert.config()
        dm = DatabaseMonitor.objects.filter(
            database=db,
            layer=0,
            time__gte=time_now() - timedelta(seconds=config.current_monitor_time_limit)
        ).order_by('time').last()
        if not dm:
            return None
        metrics = DatabaseFullMetrics.init(dm)
        metrics.update(db.data)
        return metrics

    @cached_function
    def get_cache_metrics(self, alias: str) -> Optional["CacheFullMetrics"]:
        from utilmeta.ops.models import CacheMonitor, Resource
        from utilmeta.ops.query import CacheFullMetrics

        cache: Resource = self.get_caches().filter(
            models.Q(ident=alias) | models.Q(remote_id=alias)
        ).first()
        if not cache:
            return None
        config = Alert.config()
        cm = CacheMonitor.objects.filter(
            cache=cache,
            layer=0,
            time__gte=time_now() - timedelta(seconds=config.current_monitor_time_limit)
        ).order_by('time').last()
        if not cm:
            return None
        metrics = CacheFullMetrics.init(cm)
        metrics.update(cache.data)
        return metrics

    # METRICS ----------------------------
    @alert_metric(
        ResourceType.server,
        metric_type=MetricType.usage,
        value_type=ValueType.percentage,
        min_value=0,
        max_value=100,
        default_exceed=True
    )
    def cpu_percent(self) -> float:
        metrics = self.get_current_server_metrics()
        if metrics:
            return metrics.cpu_percent
        from utilmeta.ops import Operations
        config = Operations.config()
        return psutil.cpu_percent(interval=config.monitor.default_cpu_interval if config.monitor else 1)

    @alert_metric(
        ResourceType.server,
        metric_type=MetricType.usage,
        value_type=ValueType.percentage,
        min_value=0,
        max_value=100,
        default_exceed=True
    )
    def memory_percent(self) -> float:
        metrics = self.get_current_server_metrics()
        if metrics:
            return metrics.memory_percent
        mem = psutil.virtual_memory()
        return 100 * mem.used / mem.total

    @alert_metric(
        ResourceType.server,
        metric_type=MetricType.usage,
        value_type=ValueType.numeric,
        unit='bytes',
        min_value=0,
        default_exceed=True
    )
    def used_memory(self) -> int:
        metrics = self.get_current_server_metrics()
        if metrics:
            return metrics.used_memory
        mem = psutil.virtual_memory()
        return mem.used

    @alert_metric(
        ResourceType.server,
        metric_type=MetricType.usage,
        value_type=ValueType.percentage,
        min_value=0,
        max_value=100,
        default_exceed=True
    )
    def disk_percent(self) -> float:
        metrics = self.get_current_server_metrics()
        if metrics:
            return metrics.disk_percent
        disk = psutil.disk_usage(os.getcwd())
        return 100 * disk.used / disk.total

    @alert_metric(
        ResourceType.server,
        metric_type=MetricType.usage,
        value_type=ValueType.numeric,
        default_exceed=True
    )
    def used_space(self) -> float:
        metrics = self.get_current_server_metrics()
        if metrics:
            return metrics.used_space
        disk = psutil.disk_usage(os.getcwd())
        return disk.used

    @alert_metric(
        ResourceType.server,
        metric_type=MetricType.load,
        value_type=ValueType.count,
        min_value=0,
        default_exceed=True
    )
    def net_connections(self) -> int:
        metrics = self.get_current_server_metrics()
        if metrics:
            return metrics.total_net_connections
        total, active, info = get_sys_net_connections_info()
        return max(total, 0)

    @alert_metric(
        ResourceType.server,
        metric_type=MetricType.load,
        value_type=ValueType.count,
        min_value=0,
        default_exceed=True
    )
    def idle_net_connections(self) -> int:
        metrics = self.get_current_server_metrics()
        if metrics:
            return max(metrics.total_net_connections - metrics.active_net_connections, 0)
        total, active, info = get_sys_net_connections_info()
        return max(total - active, 0)

    @alert_metric(
        ResourceType.server,
        metric_type=MetricType.load,
        value_type=ValueType.percentage,
        min_value=0,
        default_exceed=True
    )
    def idle_net_connections_percent(self) -> float:
        metrics = self.get_current_server_metrics()
        if metrics:
            if not metrics.total_net_connections:
                return 0
            return (max(metrics.total_net_connections - metrics.active_net_connections, 0) * 100 /
                    metrics.total_net_connections)
        total, active, info = get_sys_net_connections_info()
        if not total:
            return 0
        return max(total - active, 0) * 100 / total

    @alert_metric(
        ResourceType.server,
        metric_type=MetricType.usage,
        value_type=ValueType.count,
        min_value=0,
        default_exceed=True
    )
    def file_descriptors(self) -> int:
        metrics = self.get_current_server_metrics()
        if metrics:
            return metrics.file_descriptors
        return get_system_fds()

    @alert_metric(
        ResourceType.server,
        metric_type=MetricType.load,
        value_type=ValueType.numeric,
        min_value=0,
        default_exceed=True
    )
    def load_avg_1(self) -> float:
        metrics = self.get_current_server_metrics()
        if metrics:
            return metrics.load_avg_1
        try:
            l1, l5, l15 = psutil.getloadavg()
        except (AttributeError, OSError):
            l1, l5, l15 = 0, 0, 0
        return l1

    @alert_metric(
        ResourceType.server,
        metric_type=MetricType.load,
        value_type=ValueType.numeric,
        min_value=0,
        default_exceed=True
    )
    def load_avg_5(self) -> float:
        metrics = self.get_current_server_metrics()
        if metrics:
            return metrics.load_avg_5
        try:
            l1, l5, l15 = psutil.getloadavg()
        except (AttributeError, OSError):
            l1, l5, l15 = 0, 0, 0
        return l5

    @alert_metric(
        ResourceType.server,
        metric_type=MetricType.load,
        value_type=ValueType.numeric,
        min_value=0,
        default_exceed=True
    )
    def load_avg_15(self) -> float:
        metrics = self.get_current_server_metrics()
        if metrics:
            return metrics.load_avg_15
        try:
            l1, l5, l15 = psutil.getloadavg()
        except (AttributeError, OSError):
            l1, l5, l15 = 0, 0, 0
        return l15

    # DB -----------------
    @alert_metric(
        ResourceType.database,
        metric_type=MetricType.usage,
        value_type=ValueType.percentage,
        min_value=0,
        max_value=100,
        default_exceed=True
    )
    def db_server_connections_percent(self, __target: str) -> float:
        metrics = self.get_database_metrics(__target)
        if not metrics or not metrics.max_server_connections:
            return 0
        if metrics.server_connections_percent is not None:
            return metrics.server_connections_percent
        return metrics.server_connections * 100 / metrics.max_server_connections

    @alert_metric(
        ResourceType.database,
        metric_type=MetricType.usage,
        value_type=ValueType.percentage,
        min_value=0,
        max_value=100,
        default_exceed=True
    )
    def db_idle_connections_percent(self, __target: str) -> float:
        metrics = self.get_database_metrics(__target)
        if not metrics or not metrics.current_connections:
            return 0
        if metrics.idle_connections_percent is not None:
            return metrics.idle_connections_percent
        return max(0.0, (metrics.current_connections - metrics.active_connections) * 100 / metrics.current_connections)

    @alert_metric(
        ResourceType.database,
        metric_type=MetricType.usage,
        value_type=ValueType.count,
        min_value=0,
        default_exceed=True
    )
    def db_server_connections(self, __target: str) -> float:
        metrics = self.get_database_metrics(__target)
        if not metrics:
            return 0
        return metrics.server_connections

    @alert_metric(
        ResourceType.database,
        metric_type=MetricType.usage,
        value_type=ValueType.numeric,
        min_value=0,
        default_exceed=True
    )
    def db_used_space(self, __target: str) -> int:
        metrics = self.get_database_metrics(__target)
        if not metrics:
            return 0
        return metrics.used_space

    @alert_metric(
        ResourceType.database,
        metric_type=MetricType.usage,
        value_type=ValueType.numeric,
        min_value=0,
        default_exceed=True
    )
    def db_server_used_space(self, __target: str) -> int:
        metrics = self.get_database_metrics(__target)
        if not metrics:
            return 0
        return metrics.server_used_space

    @alert_metric(
        ResourceType.database,
        metric_type=MetricType.load,
        value_type=ValueType.numeric,
        min_value=0,
        default_exceed=True
    )
    def db_qps(self, __target: str) -> float:
        metrics = self.get_database_metrics(__target)
        if not metrics:
            return 0
        return metrics.qps

    # CACHE --------------

    @alert_metric(
        ResourceType.cache,
        metric_type=MetricType.usage,
        value_type=ValueType.numeric,
        unit='bytes',
        min_value=0,
        default_exceed=True
    )
    def cache_used_memory(self, __target: str) -> int:
        metrics = self.get_cache_metrics(__target)
        if not metrics:
            return 0
        return metrics.used_memory

    @alert_metric(
        ResourceType.cache,
        metric_type=MetricType.usage,
        value_type=ValueType.percentage,
        min_value=0,
        max_value=100,
        default_exceed=True
    )
    def cache_memory_percent(self, __target: str) -> float:
        metrics = self.get_cache_metrics(__target)
        if not metrics:
            return 0
        return metrics.memory_percent

    @alert_metric(
        ResourceType.cache,
        metric_type=MetricType.usage,
        value_type=ValueType.percentage,
        min_value=0,
        max_value=100,
        default_exceed=True
    )
    def cache_cpu_percent(self, __target: str) -> float:
        metrics = self.get_cache_metrics(__target)
        if not metrics:
            return 0
        return metrics.cpu_percent

    @alert_metric(
        ResourceType.cache,
        metric_type=MetricType.load,
        value_type=ValueType.numeric,
        min_value=0,
        default_exceed=True
    )
    def cache_qps(self, __target: str) -> float:
        metrics = self.get_cache_metrics(__target)
        if not metrics:
            return 0
        return metrics.qps

    # INSTANCE -----------
    @alert_metric(
        ResourceType.api,
        metric_type=MetricType.load,
        value_type=ValueType.numeric,
        min_value=0,
        default_exceed=True
    )
    def rps(self) -> float:
        metrics = self.get_current_instance_metrics()
        if not metrics:
            return 0
        return metrics.rps

    @alert_metric(
        ResourceType.api,
        metric_type=MetricType.duration,
        value_type=ValueType.numeric,
        aggregation_type=AggregationType.avg,
        unit='ms',
        min_value=0,
        default_exceed=True
    )
    def avg_time(self) -> float:
        metrics = self.get_current_instance_metrics()
        if not metrics:
            return 0
        return metrics.avg_time

    @alert_metric(
        ResourceType.instance,
        metric_type=MetricType.load,
        value_type=ValueType.count,
        min_value=0,
        default_exceed=True
    )
    def service_open_files(self) -> float:
        metrics = self.get_current_instance_metrics()
        if metrics:
            return metrics.open_files
        return 0

    @alert_metric(
        ResourceType.instance,
        metric_type=MetricType.usage,
        value_type=ValueType.percentage,
        min_value=0,
        max_value=100,
        default_exceed=True
    )
    def service_cpu_percent(self) -> float:
        metrics = self.get_current_instance_metrics()
        if metrics:
            return metrics.cpu_percent
        return 0

    @alert_metric(
        ResourceType.instance,
        metric_type=MetricType.usage,
        value_type=ValueType.percentage,
        min_value=0,
        max_value=100,
        default_exceed=True
    )
    def service_memory_percent(self) -> float:
        metrics = self.get_current_instance_metrics()
        if metrics:
            return metrics.memory_percent
        return 0

    @alert_metric(
        ResourceType.instance,
        metric_type=MetricType.usage,
        value_type=ValueType.numeric,
        unit='bytes',
        min_value=0,
        default_exceed=True
    )
    def service_used_memory(self) -> int:
        metrics = self.get_current_instance_metrics()
        if metrics:
            return metrics.used_memory
        return 0

    # LOGS ---------------
    # - rps
    # - errors
    # - outbound_rps
    # - outbound_errors
    # - outbound_timeouts
    # - p50_time
    # - p95_time
    # - p99_time
    # - failed_percent_in_seconds(seconds)
    # - failed_percent_in_requests(requests)
    # - status_percent_in_seconds(status, seconds)
    # - status_percent_in_requests(status, requests)

    @alert_metric(
        ResourceType.api,
        metric_type=MetricType.duration,
        value_type=ValueType.numeric,
        aggregation_type=AggregationType.p50,
        unit='ms',
        min_value=0,
        default_exceed=True
    )
    def p50_time(self, seconds: int, __target: str = None) -> float:
        logs = self.get_current_logs(__target).filter(
            time__gte=time_now() - timedelta(seconds=seconds)
        )
        requests = logs.count()
        if not requests:
            return 0
        return logs.values_list('duration', flat=True).order_by('-duration')[requests // 2]

    @alert_metric(
        ResourceType.api,
        metric_type=MetricType.duration,
        value_type=ValueType.numeric,
        aggregation_type=AggregationType.p95,
        unit='ms',
        min_value=0,
        default_exceed=True
    )
    def p95_time(self, seconds: int, __target: str = None) -> float:
        logs = self.get_current_logs(__target).filter(
            time__gte=time_now() - timedelta(seconds=seconds)
        )
        requests = logs.count()
        if not requests:
            return 0
        return logs.values_list('duration', flat=True).order_by('-duration')[requests // 20]

    @alert_metric(
        ResourceType.api,
        metric_type=MetricType.duration,
        value_type=ValueType.numeric,
        aggregation_type=AggregationType.p99,
        unit='ms',
        min_value=0,
        default_exceed=True
    )
    def p99_time(self, seconds: int, __target: str = None) -> float:
        logs = self.get_current_logs(__target).filter(
            time__gte=time_now() - timedelta(seconds=seconds)
        )
        requests = logs.count()
        if not requests:
            return 0
        return logs.values_list('duration', flat=True).order_by('-duration')[requests // 100]

    @alert_metric(
        ResourceType.api,
        metric_type=MetricType.error,
        value_type=ValueType.count,
        min_value=0,
        default_exceed=True
    )
    def failed_requests_num_in_seconds(self, seconds: int, __target: str = None) -> int:
        return self.get_current_logs(__target).filter(
            time__gte=time_now() - timedelta(seconds=seconds),
            status__gte=400
        ).count()

    @alert_metric(
        ResourceType.api,
        metric_type=MetricType.error,
        value_type=ValueType.count,
        min_value=0,
        default_exceed=True
    )
    def status_responses_num_in_seconds(self, status: int, seconds: int, __target: str = None) -> int:
        return self.get_current_logs(__target).filter(
            time__gte=time_now() - timedelta(seconds=seconds),
            status=status,
        ).count()

    @alert_metric(
        ResourceType.api,
        metric_type=MetricType.error,
        value_type=ValueType.percentage,
        min_value=0,
        max_value=100,
        default_exceed=True
    )
    def failed_requests_percent_in_seconds(self, seconds: int, __target: str = None) -> float:
        logs = self.get_current_logs(__target).filter(
            time__gte=time_now() - timedelta(seconds=seconds),
        )
        requests = logs.count()
        if not requests:
            return 0
        failed = logs.filter(status__gte=400).count()
        return round(failed * 100 / requests, 2)

    @alert_metric(
        ResourceType.api,
        metric_type=MetricType.error,
        value_type=ValueType.percentage,
        min_value=0,
        max_value=100,
        default_exceed=True
    )
    def status_responses_percent_in_seconds(self, status: int, seconds: int, __target: str = None) -> float:
        logs = self.get_current_logs(__target).filter(
            time__gte=time_now() - timedelta(seconds=seconds),
        )
        requests = logs.count()
        if not requests:
            return 0
        failed = logs.filter(status=status).count()
        return round(failed * 100 / requests, 2)


class AlertMetric:
    def __init__(self, metric: BaseMetric, *,
                 strategy: str = 'static',
                 # static      (fixed)
                 # baseline    (based on avg)
                 # derivative  (rate of change)
                 # anomaly     (3-sigma detection)
                 strategy_data: Optional[dict] = None,
                 threshold: Union[int, float] = None,
                 exceed: bool = True,
                 settings: AlertSettingsParams = None,
                 check_interval: Optional[int] = None
                 # compress_window: Optional[int] = None,
                 # parameters: dict = None,
                 # settings_id: str = None,
                 # target_id: Optional[str] = None,
                 # target_ident: Optional[str] = None,
                 # --
                 # severity: int = None,
                 ):
        self.metric = metric
        self.strategy = strategy
        self.strategy_data = strategy_data
        self.threshold = threshold
        self.exceed = exceed
        self.settings = settings or AlertSettingsParams.default()
        self.check_interval = check_interval

        self._last_check = None
        self._last_alert = None

    @property
    def target_param(self):
        return self.metric.target_param

    @property
    def registry(self):
        return self.metric.registry

    @property
    def name(self):
        return self.metric.name

    @property
    def settings_name(self):
        name = self.name
        if self.strategy != 'static':
            name += f'[{self.strategy}]'
        if self.threshold is not None:
            sign = '>' if self.exceed else '<'
            name = f'{name} {sign} {self.threshold}'
        return name

    def __call__(self, *args, **kwargs):
        return self.metric(*args, **kwargs)

    def check(self, registry: 'BaseMetricRegistry' = None):
        if self._last_check and self.check_interval and (time_now() -
                                                         self._last_check).total_seconds() < self.check_interval:
            return

        from utilmeta import service
        params = dict(self.settings.parameters or {})
        target = None
        if self.target_param:
            params['__target'] = target_id = self.settings.target_id or self.settings.target_ident
            if not target_id and self.target_param == 'required':
                # target required
                return

            target = Resource.objects.filter(
                models.Q(id=target_id) | models.Q(ident=target_id),
                service=service.name,
                node_id=store.node_id
            ).first()

        if not registry:
            registry_cls = self.metric.registry
            if registry_cls:
                registry = registry_cls()

        try:
            value = self.metric(registry, **params)
        except Exception as e:
            err = Error(e)
            err.setup()
            event.alert_check_failed(
                settings_name=self.settings_name,
                settings=dict(self.settings),
                error=str(err),
                message=err.message
            )
        else:
            trigger = False
            if self.strategy == 'static':
                if self.threshold is not None:
                    if self.exceed and value > self.threshold:
                        trigger = True
                    elif not self.exceed and value < self.threshold:
                        trigger = True
                else:
                    trigger = bool(value)

            elif self.strategy == 'baseline':
                # todo
                pass
            elif self.strategy == 'derivative':
                # todo
                pass
            elif self.strategy == 'anomaly':
                # todo
                pass

            alert = Alert.config()

            if trigger:
                self._last_alert = alert.trigger(
                    name=self.settings_name,
                    settings=self.settings,
                    triggered_value=value,
                    target=target
                )
            else:
                if not self._last_check:
                    self._last_alert = alert.get_log(
                        name=self.settings_name,
                        settings=self.settings,
                        target=target,
                    )

                if self._last_alert:
                    if (time_now() - self._last_alert.latest_time).total_seconds() > self.settings.compress_window:
                        # not trigger after compress window
                        if alert.recover(
                            settings=self.settings,
                            name=self.settings_name,
                            alert_log=self._last_alert
                        ):
                            self._last_alert = None

        self._last_check = time_now()
