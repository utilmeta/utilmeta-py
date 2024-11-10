import utype

from utilmeta.core import api, orm
from .utils import SupervisorObject, supervisor_var, WrappedResponse, opsRequire
from utilmeta.utils import time_now, convert_data_frame, exceptions, adapt_async, cached_property
from ..schema import (WorkerSchema, ServerMonitorSchema, WorkerMonitorSchema,
                      CacheMonitorSchema, DatabaseMonitorSchema,
                      InstanceMonitorSchema, DatabaseConnectionSchema)
from ..models import (ServerMonitor, Worker, InstanceMonitor, WorkerMonitor, Resource,
                      DatabaseMonitor, CacheMonitor)
from django.db import models
from utype.types import *
from utilmeta.core.orm import DatabaseConnections
from utilmeta.core.cache import CacheConnections


class ResourceData(orm.Schema[Resource]):
    id: int
    ident: str
    route: str
    service: Optional[str]
    node_id: Optional[str]
    # :type/:node/:ident
    ref: Optional[str]
    remote_id: Optional[str]
    server_id: Optional[int]
    data: dict = orm.Field(no_output=True)

    created_time: Optional[datetime]
    updated_time: Optional[datetime]
    deprecated: bool


class ServerResource(ResourceData):
    @property
    def ip(self) -> Optional[str]:
        return self.data.get('ip')

    @property
    def cpu_num(self) -> Optional[int]:
        return self.data.get('cpu_num')

    @property
    def memory_total(self) -> Optional[int]:
        return self.data.get('memory_total')

    @property
    def disk_total(self) -> Optional[int]:
        return self.data.get('disk_total')

    @property
    def system(self) -> Optional[str]:
        return self.data.get('system')

    @property
    def hostname(self) -> Optional[str]:
        return self.data.get('hostname')

    @property
    def platform(self) -> Optional[dict]:
        return self.data.get('platform')


class DatabaseResource(ResourceData):
    connections: List[DatabaseConnectionSchema] = orm.Field('database_connections', default_factory=list)

    @property
    def connected(self) -> bool:
        return self.data.get('connected') or False

    @property
    def max_server_connections(self) -> int:
        return self.data.get('max_server_connections') or 0

    @property
    def used_space(self) -> int:
        return self.data.get('used_space') or 0

    @property
    def transactions(self) -> int:
        return self.data.get('transactions') or 0

    @cached_property
    # @utype.Field(no_output=True)
    def db(self):
        return DatabaseConnections.get(self.ident)

    @property
    def name(self):
        return self.db.database_name if self.db else None

    @property
    def hostname(self):
        return self.db.host if self.db else None

    @property
    def type(self):
        return self.db.type if self.db else None

    @property
    def port(self):
        return self.db.port if self.db else None


class CacheResource(ResourceData):
    @property
    def connected(self) -> bool:
        return self.data.get('connected') or False

    @property
    def pid(self) -> Optional[int]:
        return self.data.get('pid')

    @cached_property
    # @utype.Field(no_output=True)
    def cache(self):
        return CacheConnections.get(self.ident)

    @property
    def hostname(self):
        return self.cache.host if self.cache else None

    @property
    def type(self):
        return self.cache.type if self.cache else None

    @property
    def port(self):
        return self.cache.port if self.cache else None


class InstanceResource(ResourceData):
    @property
    def backend(self) -> Optional[str]:
        return self.data.get('backend')

    @property
    def backend_version(self) -> Optional[str]:
        return self.data.get('backend_version')

    @property
    def version(self) -> Optional[str]:
        return self.data.get('version')

    @property
    def asynchronous(self) -> Optional[bool]:
        return self.data.get('asynchronous')

    @property
    def production(self) -> Optional[bool]:
        return self.data.get('production')

    @property
    def language(self) -> Optional[str]:
        return self.data.get('language')

    @property
    def language_version(self) -> Optional[str]:
        return self.data.get('language_version')


@opsRequire('metrics.view')
class ServersAPI(api.API):
    supervisor: SupervisorObject = supervisor_var
    response = WrappedResponse

    class BaseQuery(orm.Query):
        layer: int
        interval: Optional[int]
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

    def get_resources(self, type: str, id: str = None, **query):
        if self.supervisor.node_id:
            q = models.Q(
                node_id=self.supervisor.node_id,
            )
            if id:
                q &= models.Q(remote_id=id)
        else:
            from utilmeta import service
            q = models.Q(service=service.name)
            if id:
                q &= models.Q(remote_id=id) | models.Q(id=id)
        return Resource.objects.filter(
            q, type=type,
            **query
        )

    @api.get
    @adapt_async
    def get(self) -> List[ServerResource]:
        return ServerResource.serialize(
            self.get_resources(
                type='server',
            )
        )

    @api.get
    @adapt_async
    def metrics(self, query: ServerMonitorQuery, limit: int = utype.Param(None)):
        server = self.get_resources(
            type='server',
            id=query.server_id
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
        return convert_data_frame(result, keys=list(ServerMonitorSchema.__parser__.fields))

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
        instance = self.get_resources(
            type='instance',
            id=query.instance_id
        ).first()
        if not instance:
            raise exceptions.NotFound('instance not found')
        query.instance_id = instance.pk
        return WorkerSchema.serialize(query)

    class WorkerMonitorQuery(BaseQuery[WorkerMonitor]):
        worker_id: int = orm.Filter(required=True)

    @api.get('worker/metrics')
    @adapt_async
    def worker_metrics(self, query: WorkerMonitorQuery):
        return convert_data_frame(
            WorkerMonitorSchema.serialize(query)
        )

    @api.get
    @adapt_async
    def instances(self) -> List[InstanceResource]:
        return InstanceResource.serialize(
            self.get_resources(
                type='instance',
            )
        )

    class InstanceMonitorQuery(BaseQuery[InstanceMonitor]):
        instance_id: str = orm.Filter(required=True)

    @api.get('instance/metrics')
    @adapt_async
    def instance_metrics(self, query: InstanceMonitorQuery) -> dict:
        instance = self.get_resources(
            type='instance',
            id=query.instance_id
        ).first()
        if not instance:
            raise exceptions.NotFound('instance not found')
        query.instance_id = instance.pk
        return convert_data_frame(InstanceMonitorSchema.serialize(
          query
        ))

    @api.get
    @adapt_async
    def databases(self) -> List[DatabaseResource]:
        db_config = DatabaseConnections.config()
        if not db_config:
            return []
        return DatabaseResource.serialize(
            self.get_resources(
                type='database',
                ident__in=list(db_config.databases)
            )
        )

    @api.get
    @adapt_async
    def caches(self) -> List[CacheResource]:
        cache_config = CacheConnections.config()
        if not cache_config:
            return []
        return CacheResource.serialize(
            self.get_resources(
                type='cache',
                ident__in=list(cache_config.caches)
            )
        )

    class DatabaseMonitorQuery(BaseQuery[DatabaseMonitor]):
        database_id: str = orm.Filter(required=True)

    class CacheMonitorQuery(BaseQuery[CacheMonitor]):
        cache_id: str = orm.Filter(required=True)

    @api.get('database/metrics')
    @adapt_async
    def database_metrics(self, query: DatabaseMonitorQuery) -> dict:
        db = self.get_resources(
            type='database',
            id=query.database_id
        ).first()
        if not db:
            raise exceptions.NotFound('database not found')
        query.database_id = db.pk
        return convert_data_frame(DatabaseMonitorSchema.serialize(
            query
        ))

    @api.get('cache/metrics')
    @adapt_async
    def cache_metrics(self, query: CacheMonitorQuery) -> dict:
        cache = self.get_resources(
            type='cache',
            id=query.cache_id
        ).first()
        if not cache:
            raise exceptions.NotFound('cache not found')
        query.cache_id = cache.pk
        return convert_data_frame(CacheMonitorSchema.serialize(
            query
        ))
