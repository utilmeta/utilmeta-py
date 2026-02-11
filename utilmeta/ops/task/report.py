from django.db import models

from utilmeta.ops.res.metric import BaseMetric
from utilmeta.utils import replace_null, AgentOS, AgentDevice, AgentBrowser, fast_digest, pop_null, Error
from django.db.utils import DatabaseError
from django.core.exceptions import FieldError
from utype.types import *
from django.db.models.functions import TruncSecond
from utilmeta.ops.log.logger import LogLevel
from utilmeta.ops.store import store
from utilmeta.ops.schema import SupervisorReportSettingsSchema
from utilmeta.ops.alert.event import event


def user_comp_hash(user_id):
    return fast_digest(
        str(user_id),
        compress=True,
        case_insensitive=False,
        consistent=True,
        mod=2**24,
    )


def get_agent_dist(logs: models.QuerySet, exists: bool = False):
    # service logs
    try:
        os_dist = {}
        browser_dist = {}
        device_dist = {}
        for os in AgentOS.gen():
            qs = logs.filter(user_agent__os__icontains=os)
            num = qs.exists() if exists else qs.count()
            if num:
                os_dist[os] = num
        for br in AgentBrowser.gen():
            qs = logs.filter(user_agent__browser__icontains=br)
            num = qs.exists() if exists else qs.count()
            if num:
                browser_dist[br] = num
        for device in AgentDevice.gen():
            qs = logs.filter(user_agent__device=device)
            num = qs.exists() if exists else qs.count()
            if num:
                device_dist[device] = num
        return dict(os_dist=os_dist, browser_dist=browser_dist, device_dist=device_dist)
    except (DatabaseError, FieldError):
        # raise FieldError when json key lookup is not supported
        return {}


def get_user_active_time(times: List[datetime], inactivity_threshold: int, sort: bool = False) -> float:
    if not times:
        return 0
    if sort:
        times.sort()
    period = 0
    for i, t in enumerate(times):
        if not i:
            continue
        delta = (t - times[i - 1]).total_seconds()
        if delta < 0:
            continue
        period += min(delta, inactivity_threshold)
    return abs(period)


class ReportGenerator:
    def __init__(
        self,
        service: str,
        to_time: datetime,
        layer: int,
        settings: SupervisorReportSettingsSchema
    ):
        self.service = service
        self.to_time = to_time
        self.layer = layer
        self.settings = settings

    @property
    def timespan(self) -> timedelta:
        return [timedelta(hours=1), timedelta(days=1)][self.layer]

    @property
    def from_time(self) -> datetime:
        return self.to_time - self.timespan

    @property
    def to_date(self) -> date:
        return (self.to_time + timedelta(hours=self.settings.utcoffset)).date()

    def aggregate_logs(
        self,
        endpoint_ident: str = None,
        user_id: str = None
    ):
        start = self.from_time
        current = self.to_time
        seconds = self.timespan.total_seconds()
        # gte ~ lt only apply to layer0, in upper layer it's gt ~ lte
        include_ips = not endpoint_ident and (self.settings.ip_report_limit
                                              if self.settings.ip_report_enabled else False)
        include_agents = not endpoint_ident and self.settings.agent_report_enabled
        include_statuses = not user_id

        from utilmeta.ops.models import ServiceLog, WorkerMonitor

        first_layer = self.layer == 0 or user_id
        query = dict(service=self.service, time__gte=start, time__lt=current)
        if endpoint_ident:
            query.update(endpoint_ident=endpoint_ident)
        if user_id:
            query.update(user_id=user_id)

        service_logs = ServiceLog.objects.filter(**query)

        if endpoint_ident or user_id or self.layer:
            total_data = service_logs.aggregate(
                requests=models.Count("id"),
                avg_time=models.Avg("duration"),
            )
            total_requests = requests = total_data.get("requests") or 0
            avg_time = total_data.get("avg_time") or 0
        else:
            worker_qs = WorkerMonitor.objects.filter(
                worker__instance__service=self.service,
                time__gte=start,
                time__lt=current
            )
            requests = service_logs.count()
            total_requests = worker_qs.aggregate(v=models.Sum("requests"))["v"] or requests
            if total_requests:
                avg_time = (
                    worker_qs.aggregate(
                        v=models.Sum(
                            models.F("avg_time") * models.F("requests"),
                            output_field=models.DecimalField(),
                        )
                          / total_requests
                    )["v"]
                    or 0
                )
            else:
                avg_time = 0

        if not total_requests:
            return

        errors = service_logs.filter(
            models.Q(level=LogLevel.ERROR) | models.Q(level__iexact="ERROR") | models.Q(status__gte=500)
        ).count()

        dict_values = {}
        aggregate_info = []

        if first_layer:
            if include_statuses:
                aggregate_info.extend(
                    [
                        ("status", "statuses", None),
                        ("level", "levels", None),
                    ]
                )
            if include_ips:
                aggregate_info.append(("ip", "ip_dist", include_ips))

        for name, field, limit in aggregate_info:
            qs = (
                service_logs.exclude(**{name: None})
                .values(name)
                .annotate(count=models.Count("id"))
            )
            if isinstance(limit, int):
                qs = qs.order_by("-count")[:limit]
            dict_values[field] = {val[name]: val["count"] for val in qs}

        service_logs_duration = service_logs.order_by("-duration")
        mean_time = service_logs_duration.values_list('duration', flat=True)[requests // 2] if requests else 0
        p95_time = service_logs_duration.values_list('duration', flat=True)[requests // 20] if requests else 0
        p99_time = service_logs_duration.values_list('duration', flat=True)[requests // 100] if requests else 0
        p999_time = service_logs_duration.values_list('duration', flat=True)[requests // 1000] if requests else 0

        if not first_layer:
            return dict(
                mean_time=mean_time,
                p95_time=p95_time,
                p99_time=p99_time,
                p999_time=p999_time,
                **replace_null(
                    service_logs.aggregate(
                        time_stddev=models.StdDev("duration"),
                        uv=models.Count("user_id", distinct=True),
                        ip=models.Count("ip", distinct=True),
                    )
                ),
            )

        if user_id:
            user_agent = service_logs.values('user_agent').annotate(
                count=models.Count('id')).order_by('-count').first() if include_agents else {}
            return dict(
                requests=total_requests,
                errors=errors,
                avg_time=avg_time,
                mean_time=mean_time,
                p95_time=p95_time,
                p99_time=p99_time,
                user_agent=user_agent,
                **dict_values,
                **replace_null(
                    service_logs.aggregate(
                        first_activity=models.Min('time'),
                        last_activity=models.Max('time'),
                        in_traffic=models.Sum("in_traffic"),
                        out_traffic=models.Sum("out_traffic"),
                    )
                ),
            )

        agent_dist = {}
        if include_agents:
            agent_dist = get_agent_dist(service_logs)
        # get MAX RPS
        max_rps = (
            service_logs.annotate(second=TruncSecond("time"))
            .values("second")
            .annotate(request_count=models.Count("id"))
            .values_list("request_count", flat=True)
            .order_by("-request_count")
            .first()
        )

        return dict(
            requests=total_requests,
            avg_time=avg_time,
            errors=errors,
            rps=round(total_requests / seconds, 2),
            mean_time=mean_time,
            p95_time=p95_time,
            p99_time=p99_time,
            p999_time=p999_time,
            max_rps=max_rps,
            **agent_dist,
            **dict_values,
            **replace_null(
                service_logs.aggregate(
                    in_traffic=models.Sum("in_traffic"),
                    out_traffic=models.Sum("out_traffic"),
                    time_stddev=models.StdDev("duration"),
                    uv=models.Count("user_id", distinct=True),
                    ip=models.Count("ip", distinct=True),
                )
            ),
        )

    def aggregate_endpoint_logs(self):
        result = {}
        for ident, endpoint in store.endpoints_map.items():
            if not endpoint.remote_id:
                continue
            data = self.aggregate_logs(
                endpoint_ident=ident,
            )
            if data:
                result[endpoint.remote_id] = data
        return result

    def aggregate_users(self):
        if not self.layer:
            return
        inactivity_threshold = self.settings.user_inactivity_threshold
        user_behaviours = self.settings.user_behaviours
        limit = self.settings.user_report_limit
        hash_id = self.settings.user_hash_id

        from utilmeta.ops.models import ServiceLog
        base_logs = ServiceLog.objects.filter(
            service=self.service,
            time__gte=self.from_time,
            time__lt=self.to_time,
        )
        users = base_logs.filter(
            user_id__isnull=False,
        ).values_list('user_id', flat=True).annotate(requests=models.Count('id')).order_by('-requests')
        if limit:
            users = users[:limit]

        result = {}
        for user_id in users:
            data = self.aggregate_logs(
                user_id=user_id,
            )
            if not data:
                continue

            logs = active_logs = base_logs.filter(user_id=user_id)
            behaviours = []
            for behaviour in user_behaviours:
                if behaviour.excluded:
                    active_logs = active_logs.exclude(behaviour.logs_q)
                else:
                    behaviour_logs = logs.filter(behaviour.logs_q)
                    behaviour_active_times = list(behaviour_logs.order_by('time').values_list('time', flat=True))
                    behaviour_active_time = get_user_active_time(
                        behaviour_active_times,
                        inactivity_threshold=behaviour.inactivity_threshold or inactivity_threshold
                    )
                    behaviour_data = dict(
                        behaviour_id=behaviour.id,
                        active_time=behaviour_active_time,
                        **behaviour_logs.aggregate(
                            requests=models.Count("id"),
                            errors=models.Count("id", filter=models.Q(
                                level=LogLevel.ERROR) |
                                                             models.Q(level__iexact="ERROR") |
                                                             models.Q(status__gte=500)),
                            avg_time=models.Avg("duration"),
                            first_activity=models.Min("time"),
                            last_activity=models.Max("time")
                        )
                    )
                    behaviours.append(behaviour_data)

            active_times = list(active_logs.order_by('time').values_list('time', flat=True))
            active_time = get_user_active_time(active_times, inactivity_threshold=inactivity_threshold)
            data.update(
                active_requests=len(active_times),
                active_time=active_time,
                behaviours=behaviours
            )
            if hash_id:
                user_id = user_comp_hash(user_id)
            result[user_id] = data
        return result

    def aggregate_monitors(self):
        if self.layer == 1:
            return None

        from utilmeta.ops.models import (Resource, ServerMonitor, InstanceMonitor, DatabaseMonitor, CacheMonitor,
                                         monitors_aggregations)
        for (resource_type, monitor_cls), aggregations in monitors_aggregations.items():
            for target in Resource.objects.filter(
                type=resource_type,
                service=self.service,
                deprecated=False
            ):
                qs = monitor_cls.objects.filter(
                    **{resource_type: target},
                    layer=0,
                    time__gt=self.from_time,
                    time__lte=self.to_time
                )
                if not qs.exists():
                    continue
                aggregation_fields = {}
                for expr, fields in aggregations.items():
                    for field in fields:
                        name = field.field.name
                        aggregation_fields[name] = expr(name)

                monitor_cls.objects.create(
                    interval=self.timespan.total_seconds(),
                    time=self.to_time,
                    layer=1,
                    **{resource_type: target},
                    **qs.aggregate(**aggregation_fields),
                )

        return dict(
            **ServerMonitor.objects.filter(
                server__service=self.service,
                server__deprecated=False,
                layer=1
            ).aggregate(
                cpu_percent=models.Avg("cpu_percent"),
                memory_percent=models.Avg("memory_percent"),
                used_memory=models.Avg("used_memory"),
                file_descriptors=models.Avg("file_descriptors"),
                active_net_connections=models.Avg("active_net_connections"),
                total_net_connections=models.Avg("total_net_connections"),
                load_avg_1=models.Avg("load_avg_1"),
                load_avg_5=models.Avg("load_avg_5"),
                load_avg_15=models.Avg("load_avg_15"),
                # --
                disk_percent=models.Max("disk_percent"),
                used_space=models.Max("used_space"),
            ),
            **DatabaseMonitor.objects.filter(
                database__service=self.service,
                database__deprecated=False,
                layer=1
            ).aggregate(
                db_used_space=models.Max('used_space'),
                db_server_used_space=models.Max('server_used_space'),
                db_server_connections=models.Avg('server_connections'),
                db_server_connections_percent=models.Avg('server_connections_percent'),
                db_idle_connections_percent=models.Avg('idle_connections_percent'),
                db_qps=models.Avg('qps'),
            ),
            **CacheMonitor.objects.filter(
                cache__service=self.service,
                cache__deprecated=False,
                layer=1
            ).aggregate(
                cache_used_memory=models.Avg('used_memory'),
                cache_cpu_percent=models.Avg('cpu_percent'),
                cache_qps=models.Avg('qps'),
            ),
            **InstanceMonitor.objects.filter(
                instance__service=self.service,
                instance__deprecated=False,
                layer=1
            ).aggregate(
                service_cpu_percent=models.Avg('cpu_percent'),
                service_memory_percent=models.Avg('memory_percent'),
                service_used_memory=models.Avg('used_memory'),
                service_avg_workers=models.Avg('avg_workers'),
            )
        )

    def report_metrics(self):
        result = {}
        registry_metrics = {}
        for metric in store.report_metrics:
            if self.layer == 0:
                if metric.time_unit != 'hour':
                    continue
            elif self.layer == 1:
                # day start (at report_settings.utcoffset)
                if metric.time_unit == 'hour':
                    continue
                elif metric.time_unit == 'day':
                    pass
                elif metric.time_unit == 'week':
                    if self.to_date.weekday():
                        # not 1day of week
                        continue
                elif metric.time_unit == 'month':
                    if self.to_date.day != 1:
                        # month begin
                        continue
                elif metric.time_unit == 'quarter':
                    if self.to_date.day != 1 or (self.to_date.month % 3) != 1:
                        # quarter begin
                        continue
                elif metric.time_unit == 'year':
                    if self.to_date.month != 1 or self.to_date.day != 1:
                        # year begin
                        continue

            registry_metrics.setdefault(metric.registry, []).append(metric)

        for registry_cls, metrics in registry_metrics.items():
            registry = registry_cls(self.to_time) if registry_cls else None
            for metric in metrics:
                metric: BaseMetric
                try:
                    value = metric(registry)
                except Exception as e:
                    err = Error(e)
                    err.setup()
                    print(f'{self.__class__.__name__}: Calculate report metric [{metric.name}] failed:')
                    print(err.full_info)
                    event.report_metric_failed(
                        metric_name=metric.name,
                        metric_ref=metric.ref,
                        to_time=self.to_time,
                        error=str(err),
                        message=err.message
                    )
                    value = None
                if value is None:
                    continue
                result[metric.name] = value
        return result

    def generate(self) -> dict:
        service_data = self.aggregate_logs() or None
        system_data = None
        endpoints = None
        users = None
        metrics = None

        if service_data:
            endpoint_report_enabled = self.settings.endpoint_hourly_report_enabled if self.layer == 0 else \
                self.settings.endpoint_daily_report_enabled

            if endpoint_report_enabled:
                endpoints = self.aggregate_endpoint_logs() or None

            if self.layer == 1:
                if self.settings.user_report_enabled:
                    # aggregate user logs
                    users = self.aggregate_users() or None

        if self.settings.metrics_report_enabled:
            metrics = self.report_metrics() or None

        if self.layer == 0 and self.settings.system_report_enabled:
            system_data = self.aggregate_monitors() or None

        return pop_null(dict(
            service=service_data,
            system=system_data,
            endpoints=endpoints,
            users=users,
            metrics=metrics
        ))

    def __call__(self):
        return self.generate()
