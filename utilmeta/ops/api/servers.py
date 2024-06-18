import utype

from utilmeta.core import api, orm
from .utils import SupervisorObject, supervisor_var, WrappedResponse, opsRequire
from utilmeta.utils import time_now, convert_data_frame, exceptions, adapt_async
from ..schema import WorkerSchema, ServerMonitorSchema, WorkerMonitorSchema, InstanceMonitorSchema
from ..models import ServerMonitor, Worker, InstanceMonitor, WorkerMonitor, Resource
from django.db import models
from datetime import datetime, timedelta


@opsRequire('metrics.view')
class ServersAPI(api.API):
    supervisor: SupervisorObject = supervisor_var
    response = WrappedResponse

    class BaseQuery(orm.Query):
        start: datetime = orm.Filter(query=lambda v: models.Q(time__gte=v))
        end: datetime = orm.Filter(query=lambda v: models.Q(time__lte=v))
        within_hours: int = orm.Filter(query=lambda v: models.Q(
            time__gte=time_now() - timedelta(hours=v)))
        within_days: int = orm.Filter(query=lambda v: models.Q(
            time__gte=time_now() - timedelta(days=v)))

    class ServerMonitorQuery(BaseQuery[ServerMonitor]):
        # server_id: str = orm.Filter('server.remote_id')
        server_id: str = orm.Filter(required=True, alias_from=['server'])
        layer: int = orm.Filter(default=0)

    @api.get
    @adapt_async
    def metrics(self, query: ServerMonitorQuery, limit: int = utype.Param(None)):
        server = Resource.objects.filter(
            type='server',
            node_id=self.supervisor.node_id,
            remote_id=query.server_id
        ).first()
        if not server:
            raise exceptions.NotFound('server not found')
        query.server_id = server.pk
        if limit:
            qs = query.get_queryset().order_by('-time')[:limit]
        else:
            qs = query
        result = ServerMonitorSchema.serialize(qs)
        if limit:
            result.reverse()
        return convert_data_frame(result)

    class WorkerQuery(orm.Query[Worker]):
        # instance_id: str = orm.Filter('instance.remote_id')
        instance_id: str = orm.Filter(required=True)
        # server_id: str = orm.Filter('server.remote_id')
        status: str = orm.Filter()
        pid: int = orm.Filter()
        connected: bool = orm.Filter(default=True)

    @api.get
    @adapt_async
    def workers(self, query: WorkerQuery):
        instance = Resource.objects.filter(
            type='instance',
            node_id=self.supervisor.node_id,
            remote_id=query.instance_id
        ).first()
        if not instance:
            raise exceptions.NotFound('instance not found')
        query.instance_id = instance.pk
        return WorkerSchema.serialize(query)

    class WorkerMonitorQuery(BaseQuery[WorkerMonitor]):
        worker_id: int = orm.Filter(required=True)

    @api.get('worker/metrics')
    def worker_metrics(self, query: WorkerMonitorQuery):
        return convert_data_frame(
            WorkerMonitorSchema.serialize(query)
        )

    class InstanceMonitorQuery(BaseQuery[InstanceMonitor]):
        instance_id: int = orm.Filter(required=True)

    @api.get('instance/metrics')
    @adapt_async
    def instance_metrics(self, query: InstanceMonitorQuery):
        instance = Resource.objects.filter(
            type='instance',
            node_id=self.supervisor.node_id,
            remote_id=query.instance_id
        ).first()
        if not instance:
            raise exceptions.NotFound('instance not found')
        query.instance_id = instance.pk
        return convert_data_frame(InstanceMonitorSchema.serialize(
          query
        ))

    @api.get('database/connections')
    def database_connections(self):
        pass

    @api.get('database/metrics')
    def database_metrics(self):
        pass

    @api.get('cache/metrics')
    def cache_metrics(self):
        pass
