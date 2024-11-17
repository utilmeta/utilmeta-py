from .utils import SupervisorObject, supervisor_var, WrappedResponse, opsRequire, config
import utype

from utilmeta.core import api, orm
from ..query import ServiceLogSchema, ServiceLogBase
from utilmeta.utils import exceptions, convert_data_frame, adapt_async
from ..models import ServiceLog
from django.db import models
from utype.types import *

AGGREGATION_FIELDS = [
    'method',
    'level',
    'status',
    'request_type'
    'response_type'
]


class LogAPI(api.API):
    supervisor: SupervisorObject = supervisor_var
    response = WrappedResponse

    @opsRequire('log.view')
    def get(self, id: int) -> ServiceLogSchema:
        try:
            return ServiceLogSchema.init(id)
        except orm.EmptyQueryset:
            raise exceptions.NotFound

    class LogQuery(orm.Query[ServiceLog]):
        __distinct__ = False
        offset: int = orm.Offset(default=None)
        page: int = orm.Page()
        rows: int = orm.Limit(default=20, le=100, alias_from=['limit'])
        endpoint_ident: str = orm.Filter()
        endpoint_like: str = orm.Filter(
            query=lambda v: models.Q(endpoint_ident__icontains=v) |
                            models.Q(endpoint_ref__icontains=v) |
                            models.Q(path__icontains=v)
        )
        method: str = orm.Filter(query=lambda v: models.Q(method__iexact=v))
        level: str = orm.Filter(query=lambda v: models.Q(level__iexact=v))
        ip: str = orm.Filter()
        user_id: str = orm.Filter()
        public: bool = orm.Filter()
        status: int = orm.Filter()
        status_gte: int = orm.Filter(query=lambda v: models.Q(status__gte=v))
        status_lte: int = orm.Filter(query=lambda v: models.Q(status__lte=v))
        time_gte: datetime = orm.Filter(query=lambda v: models.Q(time__gte=v), alias_from=['time>='])
        time_lte: datetime = orm.Filter(query=lambda v: models.Q(time__lte=v), alias_from=['time<='])

        admin: bool = orm.Filter(query=lambda v: models.Q(access_token__isnull=not v), default=False)
        request_type: str = orm.Filter()
        response_type: str = orm.Filter()
        start: int = orm.Filter(query=lambda v: models.Q(time__gte=v))
        end: int = orm.Filter(query=lambda v: models.Q(time__lte=v))
        order: str = orm.OrderBy({
            ServiceLog.time: orm.Order(),
            ServiceLog.duration: orm.Order(),
            ServiceLog.in_traffic: orm.Order(),
            ServiceLog.out_traffic: orm.Order(),
            ServiceLog.length: orm.Order(),
        }, default='-time')

    @opsRequire('log.view')
    @api.get
    @adapt_async(close_conn=config.db_alias)
    def service(self, query: LogQuery):
        base_qs = ServiceLog.objects.filter(
            service=self.supervisor.service,
        )
        if self.supervisor.node_id:
            base_qs = base_qs.filter(node_id=self.supervisor.node_id)
        return self.response(
            result=ServiceLogBase.serialize(
                query.get_queryset(base_qs)
            ),
            count=query.count(base_qs)
        )

    @opsRequire('log.view')
    @api.get('service/values')
    @adapt_async(close_conn=config.db_alias)
    def service_log_values(self, query: LogQuery):
        base_qs = ServiceLog.objects.filter(
            service=self.supervisor.service,
        )
        if self.supervisor.node_id:
            base_qs = base_qs.filter(node_id=self.supervisor.node_id)
        qs = query.get_queryset(
            base_qs
        )
        result = {}
        for field in AGGREGATION_FIELDS:
            mp = {}
            for val in qs.exclude(**{field: None}).values(field).annotate(
                    count=models.Count('id')).order_by('-count'):
                mp[val[field]] = val['count']
            result[field] = mp
        return result

    @opsRequire('log.delete')
    @adapt_async(close_conn=config.db_alias)
    def delete(self, query: LogQuery):
        qs = query.get_queryset(
            ServiceLog.objects.filter(
                service=self.supervisor.service,
                node_id=self.supervisor.node_id
            )
        )
        qs.delete()

    @opsRequire('log.view')
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
        logs = ServiceLog.objects.filter(time__gte=self.request.time - timedelta(seconds=within))
        if apis:
            logs = logs.filter(endpoint__ident__in=apis)
        aggregate_info = []
        if ips:
            aggregate_info.append(('ip', 'ip_dist', ips))
        if users:
            aggregate_info.append(('user_id', 'users', users))
        if endpoints:
            aggregate_info.append(('endpoint__ident', 'endpoints', endpoints))

        dict_values = {}
        for name, field, max_num in aggregate_info:
            dict_values[field] = {val[name]: val['count'] for val in
                                  logs.exclude(**{name: None}).values(name).annotate(
                                      count=models.Count('id')).order_by('-count')[:max_num]}

        try:
            from django.db.models.functions.datetime import ExtractMinute
            time_dist = convert_data_frame(list(logs.values(
                min=ExtractMinute(self.request.time - models.F('time'))).annotate(
                uv=models.Count('user_id', distinct=True),
                ip=models.Count('ip', distinct=True)
            ).order_by('-min').filter(min__lte=int(within / 60))), keys=['min', 'uv', 'ip'])
        except ValueError:
            # sqlite does not support extract minute
            # ValueError: Extract requires native DurationField database support.
            from django.db.models import CharField
            from django.db.models.functions import Trunc
            values = list(logs.annotate(min=Trunc('time', 'minute')).values('min').annotate(
                uv=models.Count('user_id', distinct=True),
                ip=models.Count('ip', distinct=True)
            ).order_by('min'))
            for val in values:
                val['min'] = int((self.request.time - val['min']).total_seconds() / 60)
            time_dist = convert_data_frame(values, keys=['min', 'uv', 'ip'])

        return dict(
            time_dist=time_dist,
            **dict_values,
            **logs.aggregate(
                avg_time=models.Avg('duration'),
                requests=models.Count('id'),
                errors=models.Count('id', filter=models.Q(level='ERROR')),
                uv=models.Count('user_id', distinct=True),
                ip=models.Count('ip', distinct=True),
            )
        )
