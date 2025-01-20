import warnings

import utype.utils.exceptions

from .client import SupervisorClient
from typing import Optional, List, Type
from .models import Supervisor, Resource
from .config import Operations
from .schema import (
    NodeMetadata,
    ResourcesSchema,
    InstanceSchema,
    TableSchema,
    DatabaseSchema,
    CacheSchema,
    ResourceData,
    language_version,
)
from utilmeta import UtilMeta
from utilmeta.utils import fast_digest, json_dumps, get_ip, time_now, ignore_errors
from django.db import models
import utilmeta


class ModelGenerator:
    def __init__(self, model, config: Operations):
        self.model = model
        from utilmeta.core.orm.backends.base import ModelAdaptor

        self.adaptor = ModelAdaptor.dispatch(model)
        self.config = config

    # @property
    # def ident(self):
    #     return self.model_tag(self.model, lower=True)

    def generate_fields(self):
        from utype.specs.json_schema import JsonSchemaGenerator

        fields = {}
        for f in self.adaptor.get_fields(many=False, no_inherit=True):
            name = f.column_name
            to_model = to_field = relate_name = None
            secret = self.config.is_secret(name)
            if f.is_fk:
                to_model = f.related_model.ident if f.related_model else None
                to_field = f.to_field
                relate_name = f.relate_name
                secret = False
            if f.is_pk:
                secret = False
            schema = JsonSchemaGenerator(f.rule)()
            if schema.get("type") == "boolean":
                secret = False
            data = {
                k: v
                for k, v in dict(
                    schema=schema,
                    title=f.title,
                    description=f.description,
                    primary_key=f.is_pk,
                    foreign_key=f.is_fk,
                    readonly=not f.is_writable,
                    unique=f.is_unique,
                    index=f.is_db_index,
                    null=f.is_nullable,
                    required=not f.is_optional,
                    category=f.field.__class__.__name__,
                    to_model=to_model,
                    to_field=to_field,
                    relate_name=relate_name,
                    secret=secret,
                ).items()
                if v
            }

            fields[name] = data
        return fields


class ResourcesManager:
    EXCLUDED_APPS = ["utilmeta.ops", "django.contrib.contenttypes"]
    # we reserve other models like django users sessions
    UPDATE_BATCH_SIZE = 50

    def __init__(self, service: UtilMeta = None):
        if not service:
            from utilmeta import service
        self.service = service
        self.ops_config = service.get_config(Operations)
        self.service.setup()

    def get_metadata(self):
        return NodeMetadata(
            ops_api=self.ops_config.ops_api,
            base_url=self.ops_config.base_url,
            name=self.service.name,
            title=self.service.title,
            description=self.service.description or "",
            version=self.service.version_str,
            production=self.service.production,
        )

    # @cached_property
    # def mac_address(self):
    #     return get_mac_address()

    def get_instances(self, node_id) -> List[InstanceSchema]:
        from .schema import InstanceSchema

        instances = []
        for val in Resource.filter(
            type="instance",
            node_id=node_id,
        ).order_by("created_time"):
            val: Resource
            server: Optional[Resource] = None
            if val.server_id:
                server = Resource.objects.filter(id=val.server_id).first()
            if not server:
                continue
            inst_data = val.data
            server_data = dict(server.data)
            if server.ident == self.ops_config.address:
                from .monitor import get_current_server

                inst_data.update(self.instance_data)
                server_data.update(get_current_server())
            try:
                inst = InstanceSchema(
                    remote_id=val.remote_id, server=server_data, **inst_data
                )
            except utype.exc.ParseError:
                # does not meet the latest spec
                # old version instance
                # discard it if does not upgrade
                continue
            instances.append(inst)
        return instances

    @property
    def instance_data(self):
        return dict(
            version=self.service.version_str,
            asynchronous=self.service.asynchronous,
            production=self.service.production,
            backend=self.service.backend_name,
            backend_version=self.service.backend_version,
            cwd=str(self.service.project_dir),
            # host=self.ops_config.host,
            port=self.ops_config.port,
            address=self.ops_config.address,
        )

    def get_current_instance(self) -> InstanceSchema:
        from .monitor import get_current_server

        return InstanceSchema(server=get_current_server(), **self.instance_data)

    def get_tables(self, with_model: bool = False) -> List[TableSchema]:
        # from utilmeta.core.orm.backends.base import ModelAdaptor
        from utilmeta.core.orm.backends.django import DjangoModelAdaptor

        # todo: support other than django
        from django.apps import apps, AppConfig
        from django.db.models.options import Options
        from django.db import models
        from django.db.models import QuerySet

        tables = []
        model_id_map = {}

        def get_first_base(model) -> Type[models.Model]:
            meta: Options = getattr(model, "_meta")
            parents = meta.get_parent_list()
            return parents[0] if parents else None

        def register_model(mod, label):
            meta: Options = getattr(mod, "_meta")
            if meta.auto_created or meta.abstract or meta.swappable:
                # swappable: like django.contrib.auth.models.User
                return
            if mod in model_id_map:
                return model_id_map[mod]

            base = get_first_base(mod)
            base_id = None
            if base:
                base_id = model_id_map.get(base)
                if not base_id:
                    lb = getattr(base, "_meta").app_label
                    base_id = register_model(base, label=lb)

            adaptor = DjangoModelAdaptor(mod)
            model_name = mod.__name__
            ident = adaptor.ident
            generator = ModelGenerator(mod, config=self.ops_config)
            obj = TableSchema(
                ref=f"{mod.__module__}.{mod.__name__}",
                ident=ident,
                model_backend="django",
                model_name=model_name,
                metadata=dict(
                    app_label=label,
                ),
                tags=[label],
                base=base_id,
                name=meta.db_table,
                fields=generator.generate_fields(),
                database=QuerySet(mod).db,
                model=mod if with_model else None
                # relations=generator.generate_relations(),
            )
            tables.append(obj)
            model_id_map[mod] = ident
            return ident

        for i, (key, cfg) in enumerate(apps.app_configs.items()):
            cfg: AppConfig
            if cfg.name in self.EXCLUDED_APPS:
                continue
            for name, _m in cfg.models.items():
                register_model(_m, label=cfg.label)

        return tables

    def get_databases(self):
        from .monitor import get_db_max_connections
        from utilmeta.core.orm.databases.config import DatabaseConnections

        db_config = self.service.get_config(DatabaseConnections)
        if not db_config:
            return []
        databases = []
        for alias, db in db_config.databases.items():
            databases.append(
                DatabaseSchema(
                    alias=alias,
                    engine=db.type,
                    port=db.port,
                    user=db.user,
                    name=db.database_name,
                    hostname=db.host,
                    server=get_ip(db.host, True),  # incase it is intranet
                    ops=alias == self.ops_config.db_alias,
                    max_server_connections=get_db_max_connections(alias),
                )
            )
        return databases

    def get_caches(self):
        # from utilmeta.utils import get_ip
        from utilmeta.core.cache.config import CacheConnections

        cache_config = self.service.get_config(CacheConnections)
        if not cache_config:
            return []
        caches = []
        for alias, cache in cache_config.caches.items():
            caches.append(
                CacheSchema(
                    alias=alias,
                    engine=cache.engine,
                    port=cache.port,
                    hostname=cache.host,
                    server=get_ip(cache.host, True),
                )
            )
        return caches

    def get_tasks(self):
        pass

    def get_resources(self, node_id, etag: str = None) -> Optional[ResourcesSchema]:
        instances = self.get_instances(node_id)
        included = any(inst.address == self.ops_config.address for inst in instances)
        if not included:
            instances.append(self.get_current_instance())

        data = ResourcesSchema(
            metadata=self.get_metadata(),
            openapi=self.ops_config.load_openapi(),  # use new openapi
            instances=instances,
            tables=self.get_tables(),
            databases=self.get_databases(),
            caches=self.get_caches(),
        )
        if etag:
            resources_etag = fast_digest(
                json_dumps(data), compress=True, case_insensitive=False
            )
            if etag == resources_etag:
                return None
        return data

    def save_resources(self, resources: List[ResourceData], supervisor: Supervisor):
        remote_pk_map = {
            val["remote_id"]: val["pk"]
            for val in Resource.objects.filter(
                node_id=supervisor.node_id,
            ).values("pk", "remote_id")
        }

        now = time_now()
        remote_pks = []
        remote_servers = {}
        updates = []
        creates = []
        for resource in resources:
            if resource.server_id:
                remote_servers[resource.remote_id] = resource.server_id
                resource.server_id = None

            res = dict(
                deleted_time=None,
                service=supervisor.service,
                node_id=supervisor.node_id,
                **resource,
            )

            remote_pks.append(resource.remote_id)
            if resource.remote_id in remote_pk_map:
                updates.append(
                    Resource(
                        id=remote_pk_map[resource.remote_id], updated_time=now, **res
                    )
                )
            else:
                service_q = models.Q(service=supervisor.service)
                if resource.type == "server":
                    service_q |= models.Q(service=None)
                obj = Resource.objects.filter(
                    models.Q(node_id__isnull=True)
                    | models.Q(node_id=supervisor.node_id),
                    service_q,
                    type=resource.type,
                    remote_id=None,
                    ident=resource.ident,
                ).first()
                obj: Resource
                if obj:
                    _data = dict(obj.data)
                    if resource.data:
                        _data.update(resource.data)
                        resource.data = _data

                    updates.append(Resource(id=obj.pk, updated_time=now, **res))
                    continue

                creates.append(Resource(**res))

        if updates:
            fields = [
                "server_id",
                "ident",
                "route",
                "deleted_time",
                "updated_time",
                "node_id",
                "service",
                "remote_id",
                "ref",
                "data",
            ]
            batch_size = None
            if self.ops_config.database and self.ops_config.database.is_sqlite:
                batch_size = self.UPDATE_BATCH_SIZE
            Resource.objects.bulk_update(updates, fields=fields, batch_size=batch_size)

        if creates:
            Resource.objects.bulk_create(creates, ignore_conflicts=True)

        Resource.objects.filter(
            # models.Q(remote_id=None) | (~models.Q(remote_id__in=remote_pks)),
            node_id=supervisor.node_id,
            # includes remote_id=None
        ).exclude(remote_id__in=remote_pks).update(deleted_time=time_now())

        # Resource.objects.exclude(server__in=Resource.filter(type="server")).exclude(
        #     server=None
        # ).update(server_id=None)

        for remote_id, server_id in remote_servers.items():
            server = Resource.filter(
                models.Q(node_id__isnull=True) | models.Q(node_id=supervisor.node_id),
                type="server",
                remote_id=server_id,
            ).first()
            if server:
                Resource.filter(
                    remote_id=remote_id,
                    node_id=supervisor.node_id,
                ).update(server=server)

    @classmethod
    def update_supervisor_service(cls, service: str, node_id: str):
        if not service or not node_id:
            return
        from utilmeta.ops import models
        from django.core.exceptions import EmptyResultSet

        for model in models.supervisor_related_models:
            try:
                model.objects.filter(node_id=node_id).exclude(service=service).update(
                    service=service
                )
            except EmptyResultSet:
                pass
            try:
                model.objects.filter(
                    service=service,
                    node_id=None,
                ).update(node_id=node_id)
            except EmptyResultSet:
                pass

    @classmethod
    def set_local_node_id(cls, node_id: str):
        from utilmeta.bin.utils import update_meta_ini_file
        from utilmeta import service

        update_meta_ini_file(node=node_id)
        service.load_meta()
        ops_config = Operations.config()
        if ops_config:
            ops_config._node_id = node_id

    def log(self, message: str, level: str = 'info', force: bool = False):
        return self.ops_config.write_task_log(message, level=level, force=force)

    def warn(self, message: str):
        return self.log(message, 'warn', force=True)

    def sync_resources(self, supervisor: Supervisor = None, force: bool = False):
        from utilmeta import service

        ops_config = Operations.config()
        if not ops_config:
            raise TypeError("Operations not configured")
        supervisors = (
            [supervisor]
            if supervisor and not supervisor.local
            else (Supervisor.filter(connected=True, local=False, service=service.name))
        )
        for supervisor in supervisors:
            if supervisor.service != service.name:
                force = True  # name changed

            if not supervisor.node_id:
                continue

            self.log(f"sync resources of [{service.name}] to supervisor[{supervisor.node_id}]...", force=True)

            with SupervisorClient(
                base_url=supervisor.base_url,
                node_key=supervisor.public_key,
                node_id=supervisor.node_id,
                fail_silently=True,
            ) as client:
                try:
                    resources = self.get_resources(
                        supervisor.node_id,
                        etag=supervisor.resources_etag if not force else None,
                    )
                except Exception as e:
                    self.warn("meta: load resources failed with error: {}".format(e))
                    continue
                if not resources:
                    self.log("[etag] resources is identical to the remote supervisor, done", force=True)
                    continue

                resp = client.upload_resources(data=resources)
                if not resp.success:
                    raise ValueError(
                        f"sync to supervisor[{supervisor.node_id}]"
                        f" failed with error: {resp.message}"
                    )

                if supervisor.service != service.name:
                    self.log(
                        f"update supervisor and resources service name to [{service.name}]", force=True
                    )
                    supervisor.service = service.name
                    supervisor.save(update_fields=["service"])
                    self.update_supervisor_service(
                        service.name, node_id=supervisor.node_id
                    )

                if not ops_config.node_id:
                    self.set_local_node_id(supervisor.node_id)
                    # force a sync, so that if it is successful
                    # we set the local node_id

                if resp.status == 304:
                    self.log("[304] resources is identical to the remote supervisor, done", force=True)
                    continue

                if resp.result.resources_etag:
                    supervisor.resources_etag = resp.result.resources_etag
                    supervisor.save(update_fields=["resources_etag"])

                self.save_resources(resp.result.resources, supervisor=supervisor)

                self.log(
                    f"sync resources to supervisor[{supervisor.node_id}] successfully", force=True
                )
                if resp.result.url:
                    if supervisor.url != resp.result.url:
                        supervisor.url = resp.result.url
                        supervisor.save(update_fields=["url"])

                    self.log(
                        f"you can visit {resp.result.url} to view the updated resources", force=True
                    )

    def get_instance(self):
        from .log import setup_locals
        from .models import Resource

        setup_locals(self.ops_config)
        from .log import _instance

        return _instance or Resource.get_current_instance()

    def init_service_resources(
        self,
        supervisor: Supervisor = None,
        instance: Resource = None,
        force: bool = False,
    ):
        if self.ops_config.proxy:
            if not instance:
                instance = self.get_instance()
            return self.register_service(supervisor=supervisor, instance=instance)
        else:
            return self.sync_resources(supervisor=supervisor, force=force)

    def register_service(
        self, supervisor: Supervisor = None, instance: Resource = None
    ):
        if not self.ops_config.proxy:
            return
        if not instance:
            return
        resources = self.get_resources(
            supervisor.node_id if supervisor else None,
            etag=supervisor.resources_etag if supervisor else None,
        )
        from .proxy import ProxyClient, RegistrySchema, RegistryResponse

        with ProxyClient(
            base_url=self.ops_config.proxy.base_url, fail_silently=True
        ) as client:
            resp = client.register_service(
                data=RegistrySchema(
                    name=self.service.name,
                    instance_id=instance.pk,
                    # remote_id=instance.remote_id,
                    address=self.ops_config.address,
                    ops_api=self.ops_config.proxy_ops_api,
                    base_url=self.ops_config.proxy_base_url,
                    cwd=str(self.service.project_dir),
                    version=self.service.version_str,
                    title=self.service.title,
                    description=self.service.description,
                    production=self.service.production,
                    asynchronous=self.service.asynchronous,
                    backend=self.service.backend_name,
                    backend_version=self.service.backend_version,
                    language="python",
                    language_version=language_version,
                    utilmeta_version=utilmeta.__version__,
                    resources=resources,
                )
            )
            if isinstance(resp, RegistryResponse):
                if resp.result.node_id:
                    from utilmeta.bin.utils import update_meta_ini_file

                    update_meta_ini_file(node=resp.result.node_id)
                    return resp.result.node_id
            else:
                warnings.warn(
                    f"register service: [{self.service.name}] to proxy: "
                    f"{self.ops_config.proxy.base_url} failed: {resp.text}"
                )
                raise ValueError(f"service register failed: {resp.text}")
