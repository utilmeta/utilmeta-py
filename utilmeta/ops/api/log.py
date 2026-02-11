from .utils import SupervisorObject, supervisor_var, WrappedResponse, opsRequire, config
import utype

from utilmeta.core import api, orm
from ..query import (ServiceLogSchema, ServiceLogBase,
                     RequestLogBase, RequestLogSchema, AlertLogBase, AlertLogSchema)
from utilmeta.utils import exceptions, convert_data_frame, adapt_async
from ..models import ServiceLog, RequestLog, AlertLog
from django.db import models
from utype.types import *

AGGREGATION_FIELDS = ["method", "level", "status", "request_type" "response_type"]


class LogAPI(api.API):
    supervisor: SupervisorObject = supervisor_var
    response = WrappedResponse

    @opsRequire("log.view")
    def get(self, id: int) -> ServiceLogSchema:
        return self.get_service_log_detail(id)

    @opsRequire("log.view")
    @api.get('service/detail')
    def get_service_log_detail(self, id: int) -> ServiceLogSchema:
        try:
            return ServiceLogSchema.init(id)
        except orm.EmptyQueryset:
            raise exceptions.NotFound

    @opsRequire("log.view")
    @api.get('request/detail')
    def get_request_log_detail(self, id: int) -> RequestLogSchema:
        try:
            return RequestLogSchema.init(id)
        except orm.EmptyQueryset:
            raise exceptions.NotFound

    @opsRequire("log.view")
    @api.get('alert/detail')
    def get_alert_log_detail(self, id: int) -> AlertLogSchema:
        try:
            return AlertLogSchema.init(id)
        except orm.EmptyQueryset:
            raise exceptions.NotFound

    class BaseLogQuery(orm.Query):
        __distinct__ = False
        offset: int = orm.Offset(default=None)
        page: int = orm.Page()
        rows: int = orm.Limit(default=20, le=100, alias_from=["limit"])
        method: str = orm.Filter(query=lambda v: models.Q(method__iexact=v))
        path: str
        path_contains: str = orm.Filter(query=lambda v: models.Q(path__contains=v))
        path_startswith: str = orm.Filter(query=lambda v: models.Q(path__startswith=v))
        path_endswith: str = orm.Filter(query=lambda v: models.Q(path__endswith=v))
        status: int = orm.Filter()
        status_gte: int = orm.Filter(query=lambda v: models.Q(status__gte=v))
        status_lte: int = orm.Filter(query=lambda v: models.Q(status__lte=v))
        time_gte: datetime = orm.Filter(
            query=lambda v: models.Q(time__gte=v), alias_from=["time>="]
        )
        time_lte: datetime = orm.Filter(
            query=lambda v: models.Q(time__lte=v), alias_from=["time<="]
        )
        instance: str = orm.Filter(
            query=lambda v: models.Q(instance_id=v) | models.Q(instance__remote_id=v)
        )
        request_type: str = orm.Filter()
        response_type: str = orm.Filter()
        start: int = orm.Filter(query=lambda v: models.Q(time__gte=v))
        end: int = orm.Filter(query=lambda v: models.Q(time__lte=v))
        order: str = orm.OrderBy(
            {
                'time': orm.Order(),
                'duration': orm.Order(),
                'in_traffic': orm.Order(),
                'out_traffic': orm.Order(),
                'length': orm.Order(),
            },
            default="-time",
        )

    class ServiceLogQuery(BaseLogQuery[ServiceLog]):
        endpoint_ident: str = orm.Filter()
        endpoint_like: str = orm.Filter(
            query=lambda v: models.Q(endpoint_ident__icontains=v)
            | models.Q(endpoint_ref__icontains=v)
            | models.Q(path__icontains=v)
        )
        level: str = orm.Filter(query=lambda v: models.Q(level__iexact=v))
        ip: str = orm.Filter()
        user_id: str = orm.Filter()
        public: bool = orm.Filter()
        admin: bool = orm.Filter(
            query=lambda v: models.Q(access_token__isnull=not v), default=False
        )

    class RequestLogQuery(BaseLogQuery[RequestLog]):
        remote_log: str
        host: str
        context_type: str
        context_id: str
        timeout_error: bool
        server_error: bool
        client_error: bool

    class AlertLogQuery(orm.Query[AlertLog]):
        __distinct__ = False
        offset: int = orm.Offset(default=None)
        page: int = orm.Page()
        rows: int = orm.Limit(default=20, le=100, alias_from=["limit"])
        start: int = orm.Filter(query=lambda v: models.Q(time__gte=v))
        end: int = orm.Filter(query=lambda v: models.Q(time__lte=v))
        order: str = orm.OrderBy(
            {
                AlertLog.time: orm.Order(),
                AlertLog.recovered_time: orm.Order(),
                AlertLog.latest_time: orm.Order(),
                AlertLog.latest_alarm_time: orm.Order(),
                AlertLog.count: orm.Order(),
                'duration': orm.Order(models.ExpressionWrapper(
                    models.F('latest_time') - models.F('time'),
                    output_field=models.DurationField()
                )),
            },
            default="-time",
        )
        instance: str = orm.Filter(
            query=lambda v: models.Q(instance_id=v) | models.Q(instance__remote_id=v)
        )
        target: str = orm.Filter(
            query=lambda v: models.Q(target_id=v) | models.Q(target__remote_id=v) | models.Q(target__ident=v)
        )
        target_type: str = orm.Filter('target.type')
        settings_id: str
        settings_name: str
        severity: int

    @property
    def log_q(self):
        if self.supervisor.node_id:
            q = models.Q(node_id=self.supervisor.node_id) | models.Q(
                service=self.supervisor.service
            )
        else:
            q = models.Q(service=self.supervisor.service)
        return q

    @opsRequire("log.view")
    @api.get('/service')
    @adapt_async(close_conn=config.db_alias)
    def get_service_logs(self, query: ServiceLogQuery) -> WrappedResponse[List[ServiceLogBase]]:
        base_qs = ServiceLog.objects.filter(self.log_q)
        logs = ServiceLogBase.serialize(query.get_queryset(base_qs))
        if config.log.hide_ip_address or config.log.hide_user_id:
            for log in logs:
                if config.log.hide_ip_address:
                    log.ip = "*.*.*.*" if log.ip else ""
                if config.log.hide_user_id:
                    log.user_id = "***" if log.user_id else None
        return self.response(result=logs, count=query.count(base_qs))

    @opsRequire("log.view")
    @api.get('/request')
    @adapt_async(close_conn=config.db_alias)
    def get_request_logs(self, query: RequestLogQuery) -> WrappedResponse[List[RequestLogBase]]:
        base_qs = RequestLog.objects.filter(self.log_q)
        logs = RequestLogBase.serialize(query.get_queryset(base_qs))
        return self.response(result=logs, count=query.count(base_qs))

    @opsRequire("log.view")
    @api.get('/alert')
    @adapt_async(close_conn=config.db_alias)
    def get_alert_logs(self, query: AlertLogQuery) -> WrappedResponse[List[AlertLogBase]]:
        base_qs = AlertLog.objects.filter(self.log_q)
        logs = AlertLogBase.serialize(query.get_queryset(base_qs))
        return self.response(result=logs, count=query.count(base_qs))

    @opsRequire("log.view")
    @api.get("service/values")
    @adapt_async(close_conn=config.db_alias)
    def service_log_values(self, query: ServiceLogQuery):
        base_qs = ServiceLog.objects.filter(self.log_q)
        qs = query.get_queryset(base_qs)
        result = {}
        for field in AGGREGATION_FIELDS:
            mp = {}
            for val in (
                qs.exclude(**{field: None})
                .values(field)
                .annotate(count=models.Count("id"))
                .order_by("-count")
            ):
                mp[val[field]] = val["count"]
            result[field] = mp
        return result

    @opsRequire("log.delete")
    @api.delete("service")
    @adapt_async(close_conn=config.db_alias)
    def delete_service_logs(self, query: ServiceLogQuery):
        qs = query.get_queryset(
            ServiceLog.objects.filter(
                service=self.supervisor.service, node_id=self.supervisor.node_id
            )
        )
        qs.delete()

    @opsRequire("log.delete")
    @api.delete("request")
    @adapt_async(close_conn=config.db_alias)
    def delete_request_logs(self, query: RequestLogQuery):
        qs = query.get_queryset(
            RequestLog.objects.filter(
                service=self.supervisor.service, node_id=self.supervisor.node_id
            )
        )
        qs.delete()

    @opsRequire("log.view")
    @api.get
    @adapt_async(close_conn=config.db_alias)
    def realtime(
        self,
        within: int = utype.Param(3600, ge=1, le=7200),
        # agent: bool = False,
        apis: List[str] = None,
        ips: int = 0,
        users: int = 0,
        endpoints: int = 0,
    ):
        logs = ServiceLog.objects.filter(
            self.log_q, time__gte=self.request.time - timedelta(seconds=within)
        )
        if apis:
            logs = logs.filter(endpoint__ident__in=apis)
        aggregate_info = []
        if ips:
            aggregate_info.append(("ip", "ip_dist", ips))
        if users:
            aggregate_info.append(("user_id", "users", users))
        if endpoints:
            aggregate_info.append(("endpoint__ident", "endpoints", endpoints))

        dict_values = {}
        for name, field, max_num in aggregate_info:
            dict_values[field] = {
                val[name]: val["count"]
                for val in logs.exclude(**{name: None})
                .values(name)
                .annotate(count=models.Count("id"))
                .order_by("-count")[:max_num]
            }

        try:
            from django.db.models.functions.datetime import ExtractMinute

            time_dist = convert_data_frame(
                list(
                    logs.values(min=ExtractMinute(self.request.time - models.F("time")))
                    .annotate(
                        uv=models.Count("user_id", distinct=True),
                        ip=models.Count("ip", distinct=True),
                    )
                    .order_by("-min")
                    .filter(min__lte=int(within / 60))
                ),
                keys=["min", "uv", "ip"],
            )
        except ValueError:
            # sqlite does not support extract minute
            # ValueError: Extract requires native DurationField database support.
            from django.db.models import CharField
            from django.db.models.functions import Trunc

            values = list(
                logs.annotate(min=Trunc("time", "minute"))
                .values("min")
                .annotate(
                    uv=models.Count("user_id", distinct=True),
                    ip=models.Count("ip", distinct=True),
                )
                .order_by("min")
            )
            for val in values:
                val["min"] = int((self.request.time - val["min"]).total_seconds() / 60)
            time_dist = convert_data_frame(values, keys=["min", "uv", "ip"])

        return dict(
            time_dist=time_dist,
            **dict_values,
            **logs.aggregate(
                avg_time=models.Avg("duration"),
                requests=models.Count("id"),
                errors=models.Count("id", filter=models.Q(level="ERROR")),
                uv=models.Count("user_id", distinct=True),
                ip=models.Count("ip", distinct=True),
            )
        )
