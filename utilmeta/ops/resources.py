from .client import SupervisorClient
from typing import Optional, List, Type
from .models import Supervisor, Resource
from .config import Operations
from .schema import NodeMetadata, ResourcesSchema, \
    InstanceSchema, ServerSchema, TableSchema, DatabaseSchema, CacheSchema
from utilmeta import UtilMeta


class ModelGenerator:
    def __init__(self, model):
        self.model = model
        from utilmeta.core.orm.backends.base import ModelAdaptor
        self.adaptor = ModelAdaptor.dispatch(model)

    # @property
    # def ident(self):
    #     return self.model_tag(self.model, lower=True)

    def generate_fields(self):
        from utype.specs.json_schema import JsonSchemaGenerator
        fields = {}
        for f in self.adaptor.get_fields(many=False):
            name = f.column_name
            to_model = to_field = relate_name = None

            if f.is_fk:
                to_model = f.related_model.ident if f.related_model else None
                to_field = f.to_field
                relate_name = f.relate_name

            schema = JsonSchemaGenerator(f.rule)()
            data = dict(
                schema=schema,
                primary_key=f.primary_key,
                foreign_key=f.is_fk,
                readonly=not f.editable,
                unique=f.unique,
                index=f.db_index,
                null=f.null,
                required=not f.is_optional,
                category=f.__class__.__name__,
                verbose_name=f.verbose_name,
                to_model=to_model,
                to_field=to_field,
                relate_name=relate_name
            )

            fields[name] = data
        return fields

    # def get_relate_model_tag(self, related_model):
    #     meta = getattr(self.model, '_meta')
    #     app = meta.app_label
    #     if isinstance(related_model, str):
    #         if related_model == 'self':
    #             return self.model_tag(self.model, lower=True)
    #         return related_model.lower() if '.' in related_model \
    #             else f'{app}.{related_model.lower()}'
    #     return self.model_tag(related_model, lower=True)

    # def generate_relations(self):
    #     relations = {}
    #     from django.db.models import ManyToManyRel, ManyToManyField
    #     for field in self.adaptor.get_fields(many=True):
    #         if not field.is_many:
    #             continue
    #
    #         rel: ManyToManyRel = field.remote_field if isinstance(field, ManyToManyField) else field
    #         many = field if isinstance(field, ManyToManyField) else field.remote_field
    #
    #         name = field.get_cache_name()
    #         relate_name = field.remote_field.get_cache_name()
    #         through_model = through_table = through_fields = None
    #
    #         if isinstance(rel, ManyToManyRel):
    #             if rel.through:
    #                 through_model = self.get_relate_model_tag(rel.through)
    #                 if issubclass(rel.through, Model):
    #                     through_table = getattr(rel.through, '_meta').db_table
    #
    #             if rel.through_fields:
    #                 through_fields = list(rel.through_fields)
    #
    #         if isinstance(many, ManyToManyField) and not through_table:
    #             through_table = many.db_table
    #
    #         relations[name] = dict(
    #             to_model=self.get_relate_model_tag(field.related_model),
    #             relate_name=relate_name,
    #             symmetrical=rel.symmetrical,
    #             through_fields=through_fields,
    #             through_table=through_table,
    #             through_model=through_model
    #         )
    #     return relations


class ResourcesManager:
    def __init__(self, service: UtilMeta = None):
        if not service:
            from utilmeta import service
        self.service = service
        self.ops_config = service.get_config(Operations)
        self.service.setup()

    def get_metadata(self):
        return NodeMetadata(
            ops_api=self.ops_config.ops_api,
            base_url=self.service.base_url,
            name=self.service.name,
            description=self.service.description,
            version=self.service.version_str,
            production=self.service.production
        )

    @classmethod
    def get_instances(cls, node_id) -> List[InstanceSchema]:
        from .schema import InstanceSchema
        instances = []
        for val in Resource.objects.filter(
            type='instance',
            node_id=node_id,
            deleted=False
        ).order_by('created_time'):
            val: Resource
            server: Optional[Resource] = None
            if val.server_id:
                server = Resource.objects.filter(
                    id=val.server_id
                ).first()
            if not server:
                continue
            instances.append(
                InstanceSchema(
                    remote_id=val.remote_id,
                    server=server.data,
                    **val.data
                )
            )
        return instances

    def get_current_instance(self) -> InstanceSchema:
        from .monitor import get_server_statics
        server = ServerSchema(
            ip=self.service.ip,
            **get_server_statics(),
        )
        return InstanceSchema(
            server=server,
            asynchronous=self.service.asynchronous,
            production=self.service.production,
            backend=self.service.backend_name,
            backend_version=self.service.backend_version
        )

    @classmethod
    def get_tables(cls) -> List[TableSchema]:
        # todo: support other than django
        from django.apps import apps, AppConfig
        from django.db.models.options import Options
        from django.db import models

        tables = []
        model_id_map = {}

        def get_first_base(model) -> Type[models.Model]:
            from django.db.models.options import Options
            meta: Options = getattr(model, '_meta')
            parents = meta.get_parent_list()
            return parents[0] if parents else None

        def register_model(mod, label):
            meta: Options = getattr(mod, '_meta')
            if meta.auto_created or meta.abstract:
                return
            if mod in model_id_map:
                return model_id_map[mod]

            base = get_first_base(mod)
            base_id = None
            if base:
                base_id = model_id_map.get(base)
                if not base_id:
                    lb = getattr(base, '_meta').app_label
                    base_id = register_model(base, label=lb)

            model_name = mod.__name__
            ident = f'{label}.{model_name}'.lower()
            generator = ModelGenerator(mod)
            obj = TableSchema(
                ref=f'{mod.__module__}.{mod.__name__}',
                ident=ident,
                model_backend='django',
                model_name=model_name,
                metadata=dict(
                    app_label=label,
                ),
                base=base_id,
                name=meta.db_table,
                fields=generator.generate_fields(),
                # relations=generator.generate_relations(),
            )
            tables.append(obj)
            model_id_map[mod] = ident
            return ident

        for i, (key, cfg) in enumerate(apps.app_configs.items()):
            cfg: AppConfig
            if any([cfg.name.startswith(fm + '.') for fm in ('django', 'utilmeta')]):
                continue
            for name, _m in cfg.models.items():
                register_model(_m, label=cfg.label)

        return tables

    @classmethod
    def get_db_max_connections(cls, using: str) -> int:
        from django.db import connections
        db_sql = {
            'postgres': "SHOW max_connections;",
            'mysql': 'SHOW VARIABLES LIKE "max_connections";'
        }
        with connections[using].cursor() as cursor:
            db_type: str = str(cursor.db.display_name).lower()
            if db_type not in db_sql:
                return 0
            cursor.execute(db_sql[db_type])
            return int(cursor.fetchone()[0])

    def get_databases(self):
        from utilmeta.utils import get_ip
        from utilmeta.core.orm.databases.config import DatabaseConnections
        db_config = self.service.get_config(DatabaseConnections)
        databases = []
        for alias, db in db_config.databases.items():
            databases.append(
                DatabaseSchema(
                    alias=alias,
                    engine=db.engine,
                    port=db.port,
                    user=db.user,
                    hostname=db.host,
                    server=get_ip(db.host, True),
                    ops=alias == self.ops_config.db_alias,
                    max_server_connections=self.get_db_max_connections(alias)
                )
            )
        return databases

    def get_caches(self):
        from utilmeta.utils import get_ip
        from utilmeta.core.cache.config import CacheConnections
        cache_config = self.service.get_config(CacheConnections)
        databases = []
        for alias, cache in cache_config.caches.items():
            databases.append(
                CacheSchema(
                    alias=alias,
                    engine=cache.engine,
                    port=cache.port,
                    hostname=cache.host,
                    server=get_ip(cache.host, True),
                )
            )
        return databases

    def get_tasks(self):
        pass

    def get_resources(self, node_id, etag: str = None) -> ResourcesSchema:
        from utilmeta.core.api.specs.openapi import OpenAPI
        from utilmeta import service
        openapi = OpenAPI(service)()
        instances = self.get_instances(node_id)
        included = False
        for inst in instances:
            if inst.server.ip == service.ip:
                included = True
                break
        if not included:
            instances.append(self.get_current_instance())

        data = ResourcesSchema(
            metadata=self.get_metadata(),
            openapi=openapi,
            instances=instances,
            tables=self.get_tables(),
            databases=self.get_databases(),
            caches=self.get_caches()
        )
        if etag:
            pass
        return data

    def sync_resources(self, supervisor: Supervisor = None, force: bool = False):
        from utilmeta import service
        ops_config = Operations.config()
        if not ops_config:
            raise TypeError('Operations not configured')

        for supervisor in [supervisor] if supervisor else Supervisor.objects.filter(
            service=service.name,
            disabled=False,
            connected=True,
        ):
            if not supervisor.node_id or not supervisor.public_key:
                continue
            print(f'sync resources of [{service.name}] to supervisor[{supervisor.node_id}]...')
            with SupervisorClient(
                base_url=supervisor.base_url,
                node_key=supervisor.public_key,
                node_id=supervisor.node_id,
            ) as client:
                resources = self.get_resources(
                    supervisor.node_id,
                    etag=supervisor.resources_etag if not force else None
                )
                if not resources:
                    continue

                resp = client.upload_resources(
                    data=resources
                )
                if not resp.success:
                    raise ValueError(f'sync to supervisor[{supervisor.node_id}]'
                                     f' failed with error: {resp.message}')
