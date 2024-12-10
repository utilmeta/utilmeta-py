import threading
from utilmeta.conf import Config
from utilmeta.core.orm.databases.config import Database, DatabaseConnections
from utype.types import *
from utilmeta.utils import (
    DEFAULT_SECRET_NAMES,
    url_join,
    localhost,
    HTTPMethod,
    get_ip,
    cached_property,
    import_obj,
    get_origin,
    get_server_ip,
)
from typing import Union
from urllib.parse import urlsplit
from utilmeta import UtilMeta, __version__
from . import __website__
import sys
import hashlib
import os


class Operations(Config):
    __eager__: ClassVar = True
    # setup need to execute before django settings

    NAME: ClassVar = "ops"
    REF: ClassVar = "utilmeta.ops"
    HOST: ClassVar = "utilmeta.com"
    ROUTER_NAME: ClassVar = "_OperationsDatabaseRouter"
    DEFAULT_SECRET_NAMES: ClassVar = DEFAULT_SECRET_NAMES

    Database: ClassVar = Database

    class Monitor(Config):
        worker_disabled: bool
        server_disabled: bool
        instance_disabled: bool
        database_disabled: bool
        cache_disabled: bool

        worker_retention: timedelta
        server_retention: timedelta
        instance_retention: timedelta
        database_retention: timedelta
        cache_retention: timedelta

        # WORKER_MONITOR_RETENTION = timedelta(hours=12)
        # DISCONNECTED_WORKER_RETENTION = timedelta(hours=12)
        # DISCONNECTED_INSTANCE_RETENTION = timedelta(days=3)
        # DISCONNECTED_SERVER_RETENTION = timedelta(days=3)
        # SERVER_MONITOR_RETENTION = timedelta(days=7)
        # INSTANCE_MONITOR_RETENTION = timedelta(days=7)

        def __init__(
            self,
            worker_disabled: bool = False,
            server_disabled: bool = False,
            instance_disabled: bool = False,
            database_disabled: bool = False,
            cache_disabled: bool = False,
            # ----------------------------
            worker_retention: timedelta = timedelta(hours=24),
            server_retention: timedelta = timedelta(days=7),
            instance_retention: timedelta = timedelta(days=7),
            database_retention: timedelta = timedelta(days=7),
            cache_retention: timedelta = timedelta(days=7),
        ):
            super().__init__(locals())

    class Log(Config):
        DEBUG = 0
        INFO = 1
        WARN = 2
        ERROR = 3

        store_data_level: Optional[int]
        store_result_level: Optional[int]
        store_headers_level: Optional[int]
        persist_level: int
        persist_duration_limit: Optional[int]
        exclude_methods: List[str]
        exclude_status: List[int]
        exclude_request_headers: List[str]
        exclude_response_headers: List[str]
        # if these headers show up, exclude
        default_volatile: bool
        volatile_maintain: timedelta
        # maintain: Optional[timedelta]
        hide_ip_address: bool = False
        hide_user_id: bool = False

        def __init__(
            self,
            store_data_level: Optional[int] = None,
            store_result_level: Optional[int] = None,
            store_headers_level: Optional[int] = None,
            persist_level: int = WARN,
            persist_duration_limit: Optional[int] = 5,
            exclude_methods: list = (
                HTTPMethod.OPTIONS,
                HTTPMethod.CONNECT,
                HTTPMethod.TRACE,
                HTTPMethod.HEAD,
            ),
            exclude_status: list = (),
            exclude_request_headers: List[str] = (),
            exclude_response_headers: List[str] = (),
            # if these headers show up, exclude
            default_volatile: bool = True,
            volatile_maintain: timedelta = timedelta(days=7),
            hide_ip_address: bool = False,
            hide_user_id: bool = False,
            # maintain: Optional[timedelta] = None,
            # default
            # - debug: info
            # - production: WARN
        ):
            exclude_methods = (
                [m.upper() for m in exclude_methods] if exclude_methods else []
            )
            super().__init__(locals())

    class Proxy(Config):
        base_url: str
        forward: bool = False

        def __init__(
            self,
            base_url: str,
            forward: bool = False,
        ):
            super().__init__(locals())

        @property
        def proxy_url(self):
            return url_join(self.base_url, "proxy")

    def __init__(
        self,
        route: str,
        database: Union[str, Database],
        base_url: Optional[str] = None,
        # replace service.base_url
        disabled_scope: List[str] = (),
        secret_names: List[str] = DEFAULT_SECRET_NAMES,
        trusted_hosts: List[str] = (),
        # trusted_packages: List[str] = (),
        default_timeout: int = 30,
        secure_only: bool = True,
        # local_disabled: bool = False,
        logger_cls=None,
        max_backlog: int = 100,
        # will trigger a log save if the log hits this limit
        worker_cycle: Union[int, float, timedelta] = timedelta(seconds=30),
        worker_task_cls=None,
        resources_manager_cls=None,
        # every worker cycle, a worker will do
        # - save the logs
        # - save the worker monitor
        # - the main (with min pid) worker will do the monitor tasks
        openapi=None,  # openapi paths
        monitor: Monitor = Monitor(),
        log: Log = Log(),
        report_disabled: bool = False,
        task_error_log: str = None,
        max_retention_time: Union[int, float, timedelta] = timedelta(days=90),
        local_scope: List[str] = ("*",),
        eager_migrate: bool = False,
        eager_mount: bool = False,
        # new in v2.6.5 +---------
        # token: str = None
        # proxy_url: str = None,
        # proxy_forward_requests: bool = None,
        proxy: Proxy = None,
    ):
        super().__init__(locals())

        self.route = route
        self.database = database if isinstance(database, Database) else None
        self.db_alias = database if isinstance(database, str) else "__ops"

        self.disabled_scope = set(disabled_scope)
        self.secret_names = [k.lower() for k in secret_names]
        self.trusted_hosts = list(trusted_hosts)
        # self.trusted_packages = list(trusted_packages or []) + ['django', 'utilmeta']
        self.default_timeout = default_timeout
        self.secure_only = secure_only
        # self.local_disabled = local_disabled
        self.eager_migrate = eager_migrate
        self.eager_mount = eager_mount

        if isinstance(max_retention_time, timedelta):
            max_retention_time = max_retention_time.total_seconds()
        if isinstance(worker_cycle, timedelta):
            worker_cycle = worker_cycle.total_seconds()

        self.max_retention_time = max_retention_time
        self.worker_cycle = worker_cycle
        self.worker_task_cls_string = worker_task_cls
        self.max_backlog = max_backlog
        self.external_openapi = openapi
        self.local_scope = list(local_scope or [])
        self.report_disabled = report_disabled

        if base_url:
            parsed = urlsplit(base_url)
            if not parsed.scheme:
                raise ValueError(
                    f"Operations base_url should be an absolute url, got {base_url}"
                )
        self._base_url = self.parse_base_url(base_url)

        if self.HOST not in self.trusted_hosts:
            self.trusted_hosts.append(self.HOST)
        if not isinstance(monitor, self.Monitor):
            raise TypeError(
                f"Operations monitor config must be a Monitor instance, got {monitor}"
            )
        if not isinstance(log, self.Log):
            raise TypeError(f"Operations log config must be a Log instance, got {log}")
        self.monitor = monitor
        self.log = log
        self.logger_cls_string = logger_cls
        self.resources_manager_cls_string = resources_manager_cls
        self.task_error_log = task_error_log
        # self._token = token
        self._ready = False
        self._node_id = None
        self._openapi = None
        self._task = None
        self._mounted = False
        # ------------------
        if proxy and not isinstance(proxy, self.Proxy):
            raise TypeError(
                f"Operations proxy config must be a Proxy instance, got {proxy}"
            )
        self.proxy = proxy

    @classmethod
    def parse_base_url(cls, url: str):
        if not url:
            return url
        if "$IP" in url:
            url = url.replace("$IP", get_server_ip())
        return url

    def load_openapi(self, no_store: bool = False):
        from utilmeta import service
        from utilmeta.core.api.specs.openapi import OpenAPI

        openapi = OpenAPI(
            service, external_docs=self.external_openapi, base_url=self.base_url
        )()
        if not no_store:
            self._openapi = openapi
        return openapi

    # @property
    # def token(self):
    #     return self._token

    @property
    def local_disabled(self):
        return not self.local_scope

    @property
    def is_local(self):
        return localhost(self.ops_api)

    @property
    def is_secure(self):
        return urlsplit(self.ops_api).scheme == "https"

    @property
    def proxy_required(self):
        # if self.proxy:
        #     return False
        if self.is_local:
            return False
        try:
            from ipaddress import ip_address

            hostname = urlsplit(self.base_url).hostname
            ip = get_ip(hostname)
            return ip_address(ip or self.host).is_private
        except ValueError:
            return False

    @property
    def openapi(self):
        if self._openapi is not None:
            return self._openapi
        return self.load_openapi()

    @property
    def node_id(self):
        return self._node_id

    @cached_property
    def logger_cls(self):
        from utilmeta.ops.log import Logger

        if not self.logger_cls_string:
            return Logger
        cls = import_obj(self.logger_cls_string)
        if not issubclass(cls, Logger):
            raise TypeError(
                f"Operations.logger_cls must inherit utilmeta.ops.log.Logger, got {cls}"
            )
        return cls

    @cached_property
    def resources_manager_cls(self):
        from utilmeta.ops.resources import ResourcesManager

        if not self.resources_manager_cls_string:
            return ResourcesManager
        cls = import_obj(self.resources_manager_cls_string)
        if not issubclass(cls, ResourcesManager):
            raise TypeError(
                f"Operations.logger_cls must inherit utilmeta.ops.log.Logger, got {cls}"
            )
        return cls

    @cached_property
    def worker_task_cls(self):
        from utilmeta.ops.task import OperationWorkerTask

        if not self.worker_task_cls_string:
            return OperationWorkerTask
        cls = import_obj(self.worker_task_cls_string)
        if not issubclass(cls, OperationWorkerTask):
            raise TypeError(
                f"Operations.worker_task_cls must inherit "
                f"utilmeta.ops.task.OperationWorkerTask, got {cls}"
            )
        return cls

    @classmethod
    def get_secret_key(cls, service: UtilMeta):
        seed = (
            f"{service.module_name}:{service.name}:"
            f"{service.backend_name}:{service.backend_version}:{service.base_url}:{__version__}:{sys.version}"
        )
        return hashlib.md5(seed.encode()).hexdigest()

    def hook(self, service: UtilMeta):
        from .cmd import OperationsCommand

        service.register_command(OperationsCommand)

    def setup(self, service: UtilMeta):
        if self._ready:
            return

        # --- add log middleware
        if service.adaptor:
            service.adaptor.add_middleware(self.logger_cls.middleware_cls(self))
        else:
            raise NotImplementedError(
                "Operations setup error: service backend not specified"
            )

        # from django.core.exceptions import ImproperlyConfigured
        # django_settings = None
        # try:
        #     from django.conf import settings
        #     _ = settings.INSTALLED_APPS
        # if the settings is not configured, this will trigger ImproperlyConfigured
        # except (ImportError, ImproperlyConfigured):
        #     print('NOT CONFIGURED')
        #     pass
        # else:
        #     django_settings = settings
        #     # this is a django application with settings configured
        #     # or a UtilMeta service with django settings and setup before Operations setup
        #     print('SETTINGS CONFIGURED')

        from utilmeta.core.server.backends.django.settings import DjangoSettings

        django_config = service.get_config(DjangoSettings)

        db_routers = []
        if self.db_alias != "default":
            db_router = self.get_database_router()
            setattr(service.module, self.ROUTER_NAME, db_router)
            db_routers.append(f"{service.module_name}.{self.ROUTER_NAME}")

        if django_config:
            if self.REF not in django_config.apps:
                django_config.apps.append(self.REF)
            if db_routers:
                django_config.database_routers.extend(db_routers)
        else:
            # if django_settings:
            #     # DjangoSettings not configured but a django application settings already setup
            #     pass
            django_config = DjangoSettings(
                # django_settings,
                # DjangoSettings not configured but a django application settings already setup
                apps=[self.REF],
                database_routers=tuple(db_routers),
                secret_key=self.get_secret_key(service),
                append_slash=True,
            )
            service.use(django_config)

        # --------- DATABASE
        dbs_config = service.get_config(DatabaseConnections)
        if dbs_config:
            if self.database:
                dbs_config.add_database(
                    service=service, alias=self.db_alias, database=self.database
                )
            else:
                self.database = dbs_config.databases.get(self.db_alias)
                if not self.database:
                    raise ValueError(
                        f"Operations config: database required, got invalid {repr(self.db_alias)}"
                    )
        else:
            if not self.database:
                raise ValueError(
                    f"Operations config: database required, got invalid {repr(self.db_alias)}"
                )
            service.use(DatabaseConnections({self.db_alias: self.database}))

        # setup here, before importing APIs
        django_config.setup(service)
        # ----------
        # from django.conf import settings

        # -------------- API
        # if not service.auto_created:
        # mount even for auto created service
        if not self._mounted:
            parsed = urlsplit(self.route)
            if not parsed.scheme:
                from utilmeta.ops.api import OperationsAPI

                # route instead of URL
                service.mount_to_api(
                    OperationsAPI, route=self.route, eager=self.eager_mount
                )
                self._mounted = True
            # try:
            #     root_api = service.resolve()
            # except ValueError:
            #     return
            # if inspect.isclass(root_api) and issubclass(root_api, api.API):
            #     if not issubclass(root_api, OperationsAPI):
            #         # mount the root API only
            #         try:
            #             root_api.__mount__(
            #                 OperationsAPI,
            #                 route=self.route,
            #             )
            #         except ValueError:
            #             # if already exists, quit mounting
            #             pass

        if service.meta_config:
            node_id = service.meta_config.get("node") or service.meta_config.get(
                "node-id"
            )
            if node_id:
                self._node_id = node_id

        self._ready = True

    def on_api_mount(self, service, api, route):
        self._openapi = None
        # clear openapi cache

    def on_startup(self, service: UtilMeta):
        ops_api = self.ops_api
        if not ops_api:
            return

        # load OpenAPI here:
        # (for some backend like sanic, generate docs in workers can load to errors)
        if not self._openapi:
            self.load_openapi()

        if self._task:
            print("Operations task already started, ignoring...")
            return

        if self.eager_migrate:
            # migrate must be eagerly finished before the on_startup finish
            # try migrate before load first
            # use another thread to migrate
            if service.adaptor.async_startup:
                migrate_thread = threading.Thread(target=self.migrate)
                migrate_thread.start()
                migrate_thread.join()
            else:
                self.migrate()

        print(
            f"UtilMeta OperationsAPI loaded at {ops_api}, "
            f"connect your APIs at {__website__}"
        )
        # from .log import setup_locals
        # threading.Thread(target=setup_locals, args=(self,)).start()
        # task
        task = self.worker_task_cls(self)
        thread = threading.Thread(target=task.start, daemon=True)
        # todo: protect resources of daemon thread
        thread.start()
        self._task = task

    def get_database_router(self):
        class OperationsDatabaseRouter:
            @staticmethod
            def db_for_read(model, **hints):
                if model._meta.app_label == self.NAME:
                    return self.db_alias
                return None

            @staticmethod
            def db_for_write(model, **hints):
                if model._meta.app_label == self.NAME:
                    return self.db_alias
                return None

            @staticmethod
            def allow_relation(obj1, obj2, **hints):
                return None

            @staticmethod
            def allow_migrate(db, app_label, model_name=None, **hints):
                if app_label == self.NAME:
                    return db == self.db_alias
                else:
                    if db == self.db_alias:
                        return False
                    return None

        return OperationsDatabaseRouter

    def migrate(self, with_default: bool = False):
        from utilmeta.core.orm.backends.django.database import DjangoDatabaseAdaptor

        DjangoDatabaseAdaptor(self.database).check()
        import warnings
        from django.db.migrations.executor import MigrationExecutor
        from django.db import connections

        ops_conn = connections[self.db_alias]
        executor = MigrationExecutor(ops_conn)
        migrate_apps = ["ops", "contenttypes"]
        try:
            targets = [
                key
                for key in executor.loader.graph.leaf_nodes()
                if key[0] in migrate_apps
            ]
            plan = executor.migration_plan(targets)
            if not plan:
                return
            executor.migrate(targets, plan)
        except Exception as e:
            warnings.warn(f"migrate operation models failed with error: {e}")
        if with_default:
            from django.db import connection

            # ----------
            if connection != ops_conn:
                try:
                    executor = MigrationExecutor(connection)
                    targets = [
                        key
                        for key in executor.loader.graph.leaf_nodes()
                        if key[0] in migrate_apps
                    ]
                    plan = executor.migration_plan(targets)
                    if not plan:
                        return
                    executor.migrate(targets, plan)
                except Exception as e:
                    # ignore migration in default db
                    warnings.warn(
                        f"migrate operation models to default database failed: {e}"
                    )

    @property
    def ops_api(self):
        parsed = urlsplit(self.route)
        if parsed.scheme:
            # is url
            return self.route
        if self._base_url:
            return url_join(self._base_url, self.route)
        try:
            from utilmeta import service
        except ImportError:
            return None
        return url_join(service.base_url, self.route)
        # return url_join(service.get_base_url(
        #     no_localhost=bool(self.proxy) or service.production
        # ), self.route)

    @property
    def host(self):
        ip = get_server_ip(private_only=bool(self.proxy)) or "127.0.0.1"
        try:
            from utilmeta import service
        except ImportError:
            return ip
        if not service.host or localhost(service.host):
            return ip
        return service.host

    @property
    def port(self):
        try:
            from utilmeta import service
        except ImportError:
            return None
        if self._base_url:
            parsed = urlsplit(self._base_url)
            if parsed.port:
                return parsed.port
        if service.port:
            return service.port
        if service.adaptor:
            return service.adaptor.DEFAULT_PORT
        return None

    @property
    def address(self):
        from ipaddress import ip_address

        addr = ip_address(self.host)
        port = self.port
        host = self.host
        if port:
            if addr.version == 6:
                host = f"[{host}]"
            return f"{host}:{port}"
        return host

    @property
    def base_url(self):
        if self._base_url:
            return self._base_url
        # if there is other servers mounted, base_url should fall back to origin
        try:
            from utilmeta import service
        except ImportError:
            return None
        if not service.adaptor.backend_views_empty:
            return service.origin
        return service.base_url

    @property
    def proxy_origin(self):
        return "http://" + self.address

    @property
    def proxy_ops_api(self):
        if not self.proxy:
            return self.ops_api
        parsed = urlsplit(self.route)
        try:
            from utilmeta import service
        except ImportError:
            return None
        if parsed.scheme:
            # is url
            route = parsed.path
        else:
            route = url_join(service.root_url, self.route, with_scheme=False)
        return url_join(self.proxy_origin, route)

    @property
    def proxy_base_url(self):
        if not self.proxy:
            return self.base_url
        try:
            from utilmeta import service
        except ImportError:
            return None
        origin = self.proxy_origin
        if not service.adaptor.backend_views_empty:
            return origin
        return url_join(origin, service.root_url)

    # def check_host(self):
    #     parsed = urlsplit(self.ops_api)
    #     if localhost(str(parsed.hostname)):
    #         return False
    #     return True

    def check_supervisor(self, base_url: str):
        parsed = urlsplit(base_url)
        if self.secure_only:
            if parsed.scheme not in ["https", "wss"]:
                raise ValueError(
                    f"utilmeta.ops.Operations: Insecure supervisor: {base_url}, "
                    f"HTTPS is required, or you need to turn secure_only=False"
                )
        host = str(parsed.hostname)
        for trusted in self.trusted_hosts:
            if host == trusted or host.endswith(f".{trusted}"):
                return True
        raise ValueError(
            f"utilmeta.ops.Operations: Untrusted supervisor host: {parsed.hostname}, "
            f"if you trust this host, "
            f"you need to add it to the [trusted_hosts] param of Operations config"
        )

    @classmethod
    def get_backend_name(cls, backend):
        name = str(getattr(backend, "name", ""))
        if name:
            return name
        name = str(getattr(backend, "__name__", ""))
        if not name:
            ref_name = str(backend).lstrip("<").rstrip(">").strip()
            if " " in ref_name:
                ref_name = ref_name.split(" ")[0]
            if "." in ref_name:
                ref_name = ref_name.split(".")[0]
            name = ref_name or str(backend)
        return name + "_service"

    @classmethod
    def get_service_name(cls, backend):
        from utilmeta.utils import search_file, load_ini, read_from

        meta_path = search_file("utilmeta.ini") or search_file("meta.ini")
        name = None
        if meta_path:
            try:
                config = load_ini(read_from(meta_path), parse_key=True)
            except Exception as e:
                import warnings

                warnings.warn(f"load ini file: {meta_path} failed with error: {e}")
            else:
                meta_config = config.get("utilmeta") or config.get("service") or {}
                if not isinstance(meta_config, dict):
                    meta_config = {}
                name = str(meta_config.get("name", "")).strip()
        if not name:
            name = str(getattr(backend, "name", ""))
        if name:
            return name
        if meta_path:
            return os.path.basename(os.path.dirname(meta_path))
        return cls.get_backend_name(backend)

    def integrate(self, backend, module=None, name: str = None):
        parsed = urlsplit(self.route)
        route = parsed.path
        root_url = None
        if parsed.scheme:
            # is url
            origin = get_origin(self.route)
        elif not self._base_url:
            if self.proxy:
                eg = (
                    'eg: Operations(base_url="http://$IP:8080/api"), \n you are using a cluster proxy,'
                    " $IP will be your current server ip address"
                )
            else:
                eg = 'eg: Operations(base_url="https://api.example.com/api")'
            raise ValueError(
                "Integrate utilmeta.ops.Operations requires to set a base_url of your API service, "
                + eg
            )
        else:
            url_parsed = urlsplit(self._base_url)
            # if url_parsed.path:
            #     route = url_join(url_parsed.path, route, with_scheme=False)
            origin = get_origin(self._base_url)
            root_url = url_parsed.path

        from utilmeta import UtilMeta

        try:
            from utilmeta import service
        except ImportError:
            service = UtilMeta(
                module,
                backend=backend,
                name=name or self.get_service_name(backend),
                origin=origin,
                route=root_url,
            )
            service._auto_created = True
        else:
            if not service.module_name:
                if module:
                    service.module_name = module
                else:
                    raise ValueError(
                        f"Operations.integrate second param should pass __name__, got {module}"
                    )

        service.use(self)
        service.setup()
        # import API after setup
        if service.adaptor:
            if not self._mounted:
                from .api import OperationsAPI

                service.mount_to_api(OperationsAPI, route=route, eager=self.eager_mount)
                self._mounted = True
            # service.adaptor.adapt(OperationsAPI, route=parsed.path)
            service.adaptor.setup()
        else:
            raise NotImplementedError(
                "Operations integrate error: service backend not specified"
            )

        if service.module:
            # ATTRIBUTE FINDER
            setattr(service.module, "utilmeta", service)

        import utilmeta

        if not utilmeta._cmd_env:
            # trigger start
            self.on_startup(service)

    def is_secret(self, key: str):
        for k in self.secret_names:
            if k in key.lower():
                return True
        return False

    # OpenAPI getters --------------------------------
    # @classmethod
    # def get_drf_openapi(
    #     cls,
    #     title=None, url=None, description=None, version=None
    # ):
    #     from rest_framework.schemas.openapi import SchemaGenerator
    #     generator = SchemaGenerator(title=title, url=url, description=description, version=version)
    #
    #     def generator_func(service: 'UtilMeta'):
    #         return generator.get_schema(public=True)
    #
    #     return generator_func

    @classmethod
    def get_django_ninja_openapi(cls, *ninja_apis, **path_ninja_apis):
        from ninja.openapi.schema import get_schema
        from ninja import NinjaAPI

        def generator_func(service: "UtilMeta"):
            config = service.get_config(cls)
            docs = []
            for app in ninja_apis:
                if isinstance(app, NinjaAPI):
                    docs.append(get_schema(app))
                elif isinstance(app, dict):
                    path_ninja_apis.update(app)
                else:
                    raise TypeError(
                        f"Invalid application: {app} for django ninja. NinjaAPI() instance expected"
                    )
            for path, ninja_api in path_ninja_apis.items():
                if isinstance(ninja_api, NinjaAPI):
                    doc = get_schema(ninja_api)
                    servers = doc.get("servers", [])
                    doc["servers"] = [
                        {"url": url_join(config.base_url, path)}
                    ] + servers
                    docs.append(doc)
            return docs

        return generator_func

    # @classmethod
    # def get_apiflask_openapi(cls):
    #     from apiflask import APIFlask
    #
    #     def generator_func(service: 'UtilMeta'):
    #         app = service.application()
    #         if isinstance(app, APIFlask):
    #             return app._get_spec('json', force_update=True)
    #         raise TypeError(f'Invalid application: {app} for django ninja. APIFlask() instance expected')
    #
    #     return generator_func
    #
    # @classmethod
    # def get_fastapi_openapi(cls):
    #     from fastapi import FastAPI
    #
    #     def generator_func(service: 'UtilMeta'):
    #         app = service.application()
    #         if isinstance(app, FastAPI):
    #             return app.openapi()
    #         raise TypeError(f'Invalid application: {app} for django ninja. FastAPI() instance expected')
    #
    #     return generator_func
