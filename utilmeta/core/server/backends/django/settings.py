import django
import os
import sys
from typing import Union, List

from utilmeta import UtilMeta
from utilmeta.utils import import_obj, multi
from utilmeta.conf.base import Config
from utilmeta.conf.time import Time
from utilmeta.core.orm.databases import DatabaseConnections, Database
from utilmeta.core.cache.config import CacheConnections, Cache
from django.conf import Settings, LazySettings
from django.core.exceptions import ImproperlyConfigured

DEFAULT_MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    # "django.contrib.auth.middleware.AuthenticationMiddleware",
    # "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # utilmeta middleware
    # 'utilmeta.adapt.server.backends.django.DebugCookieMiddleware'
]
DEFAULT_APPS = [
    # "django.contrib.admin",
    # "django.contrib.auth",
    "django.contrib.contenttypes",
    # "django.contrib.sessions",
    # "django.contrib.messages",
    # "django.contrib.staticfiles",
]
DEFAULT_DB_ENGINE = {
    'sqlite': 'django.db.backends.sqlite3',
    'oracle': 'django.db.backends.oracle',
    'mysql': 'django.db.backends.mysql',
    'postgres': 'django.db.backends.postgresql'
}
WSGI_APPLICATION = "WSGI_APPLICATION"
ASGI_APPLICATION = "ASGI_APPLICATION"
ROOT_URLCONF = "ROOT_URLCONF"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SETTINGS_MODULE = 'DJANGO_SETTINGS_MODULE'
DEFAULT_LANGUAGE_CODE = "en-us"
DEFAULT_TIME_ZONE = "UTC"
DEFAULT_USE_I18N = True
DEFAULT_USE_TZ = True

DB = 'django.core.cache.backends.db.DatabaseCache'
FILE = 'django.core.cache.backends.filebased.FileBasedCache'
DUMMY = 'django.core.cache.backends.dummy.DummyCache'
LOCMEM = 'django.core.cache.backends.locmem.LocMemCache'
MEMCACHED = 'django.core.cache.backends.memcached.MemcachedCache'
PYLIBMC = 'django.core.cache.backends.memcached.PyLibMCCache'
DJANGO_REDIS = 'django.core.cache.backends.redis.RedisCache'
CACHE_BACKENDS = {
    'db': DB,
    'database': DB,
    'file': FILE,
    'locmem': LOCMEM,
    'memcached': MEMCACHED,
    'redis': DJANGO_REDIS,
    'pylibmc': PYLIBMC
}


class DjangoSettings(Config):
    def __init__(
            self,
            module_name: str = None, *,
            # current settings module for django project
            root_urlconf: str = None,
            # current url conf (if there is an exists django project)
            secret_key: str = None,
            apps_package: str = None,
            # package ref (such as 'domain' / 'service.applications')
            apps: Union[tuple, List[str]] = (),
            database_routers: tuple = (),
            allowed_hosts: list = (),
            middleware: Union[tuple, List[str]] = (),
            default_autofield: str = None,
            wsgi_application: str = None,
            # time_zone: str = None,
            # use_tz: bool = None,
            user_i18n: bool = None,
            language: str = None,
            append_slash: bool = False,
            extra: dict = None,
            # urlpatterns: list = None,
    ):
        super().__init__(locals())
        self.module_name = module_name
        self.django_settings = None
        # if module_name:
        #     if isinstance(module_name, str):
        #         self.module_name = module_name
        #     elif isinstance(module_name, (Settings, LazySettings)):
        #         self.django_settings = module_name

        self.secret_key = secret_key
        self.apps_package = apps_package
        self.apps = list(apps)
        self.allowed_hosts = allowed_hosts
        self.middleware = middleware
        self.root_urlconf = root_urlconf
        self.default_autofield = default_autofield
        self.wsgi_application = wsgi_application
        # self.time_zone = DEFAULT_TIME_ZONE if time_zone is None else time_zone
        # self.use_tz = DEFAULT_USE_TZ if use_tz is None else use_tz
        self.language = DEFAULT_LANGUAGE_CODE if language is None else language
        self.use_i18n = DEFAULT_USE_I18N if user_i18n is None else user_i18n
        self.append_slash = append_slash
        self.module = None
        self.url_conf = None
        self.database_routers = list(database_routers)
        # self.urlpatterns = urlpatterns
        self._setup = False
        self._settings = {}
        self._extra_settings = extra
        self._plugin_settings = {}

        self.load_apps()

    def register(self, plugin):
        getter = getattr(plugin, 'as_django', None)
        if callable(getter):
            plugin_settings = getter()
            if not isinstance(plugin_settings, dict):
                raise TypeError(f'Invalid settings: {plugin_settings}')
            self._plugin_settings.update(plugin_settings)
            if self.module:
                # already set
                self._settings.update(plugin_settings)
                from django.conf import settings
                for attr, value in plugin_settings.items():
                    setattr(self.module, attr, value)
                    setattr(settings, attr, value)

    @property
    def apps_path(self):
        if not self.apps_package:
            return None
        package = import_obj(self.apps_package)
        return package.__path__[0]

    @classmethod
    def app_labels(cls) -> List[str]:
        from django.apps.registry import apps
        labels = []
        for key, cfg in apps.app_configs.items():
            labels.append(cfg.label)
        return labels

    def get_db(self, app_label: str):
        # TODO
        return 'default'

    def get_secret(self, service: UtilMeta):
        if self.secret_key:
            return self.secret_key
        # generate a stable random secret based on the path, this could be insecure
        # if the attacker happen to guess the key
        import platform
        import hashlib
        import warnings
        import utilmeta
        if service.production:
            raise ValueError(f'django: secret_key not set for production')
        else:
            warnings.warn('django: secret_key not set, auto generating')
        tag = f'{service.name}:{service.description}:{service.version}' \
              f'{service.backend_name}:{service.module_name}' \
              f'{django.__version__}{utilmeta.__version__}{sys.version}{platform.platform()}'.encode()
        return hashlib.sha256(tag).hexdigest()

    def load_apps(self):
        installed_apps = list(DEFAULT_APPS)
        installed_apps.extend(self.apps)

        if self.apps_package:
            apps_path = self.apps_path
            hosted_labels = [p for p in next(os.walk(apps_path))[1] if '__' not in p]
            for app in hosted_labels:
                label = f'{self.apps_package}.{app}'
                if label not in installed_apps:
                    installed_apps.append(label)

        self.apps = installed_apps
        return installed_apps

    @classmethod
    def get_cache(cls, cache: Cache):
        return {
            'BACKEND': CACHE_BACKENDS.get(cache.engine) or cache.engine,
            'LOCATION': cache.get_location(),
            'OPTIONS': cache.options or {},
            'KEY_FUNCTION': cache.key_function,
            'KEY_PREFIX': cache.prefix,
            'TIMEOUT': cache.timeout,
            'MAX_ENTRIES': cache.max_entries,
        }

    @classmethod
    def get_time(cls, time_config: Time):
        return {
            'DATETIME_FORMAT': time_config.datetime_format,
            'DATE_FORMAT': time_config.date_format,
            'TIME_ZONE': time_config.time_zone or DEFAULT_TIME_ZONE,
            'USE_TZ': time_config.use_tz,
        }

    @classmethod
    def get_database(cls, db: Database, service: UtilMeta):
        engine = db.engine
        if '.' not in db.engine:
            for name, eg in DEFAULT_DB_ENGINE.items():
                if name.lower() in engine.lower():
                    if name == 'postgres' and service.asynchronous and django.VERSION >= (4, 2):
                        # COMPAT DJANGO > 4.2
                        engine = 'utilmeta.core.server.backends.django.postgresql'
                    else:
                        engine = eg
                    break

        options = {}
        if db.ssl:
            options['sslmode'] = 'require'
        if 'sqlite' in engine:
            return {
                'ENGINE': engine,
                'NAME': db.name,
                'OPTIONS': options
            }
        return {
            'ENGINE': engine,
            'HOST': db.host,
            'PORT': db.port,
            'NAME': db.name,
            'USER': db.user,
            'TIME_ZONE': db.time_zone,
            'PASSWORD': db.password,
            'CONN_MAX_AGE': db.max_age,
            'DISABLE_SERVER_SIDE_CURSORS': db.pooled,
            'OPTIONS': options,
            # 'ATOMIC_REQUESTS': False,
            # 'AUTOCOMMIT': True,
        }

    def hook(self, service: UtilMeta):
        from .cmd import DjangoCommand
        from .adaptor import DjangoServerAdaptor
        service.register_command(DjangoCommand)
        if isinstance(service.adaptor, DjangoServerAdaptor):
            service.adaptor.settings = self
            # replace settings

    def apply_settings(self, service: UtilMeta, django_settings: Union[Settings, LazySettings]):
        self.django_settings = django_settings

        adaptor = service.adaptor
        from .adaptor import DjangoServerAdaptor
        if isinstance(adaptor, DjangoServerAdaptor):
            adaptor.settings = self

        databases = getattr(django_settings, 'DATABASES', {})
        if not isinstance(databases, dict):
            databases = {}
        caches = getattr(django_settings, 'CACHES', {})
        if not isinstance(caches, dict):
            caches = {}

        db_config = service.get_config(DatabaseConnections)
        if not db_config:
            db_config = DatabaseConnections({})
            service.use(db_config)

        cache_config = service.get_config(CacheConnections)
        if not cache_config:
            cache_config = CacheConnections({})
            service.use(cache_config)

        if databases:
            for key, val in databases.items():
                val = {str(k).lower(): v for k, v in val.items()} if isinstance(val, dict) else {}
                if not val:
                    continue
                if key not in db_config.databases:
                    db_config.add_database(service, alias=key, database=Database(
                        name=val.get('name'),
                        user=val.get('user'),
                        password=val.get('password'),
                        engine=val.get('engine'),
                        host=val.get('host'),
                        port=val.get('port'),
                        options=val.get('options'),
                    ))

        if caches:
            for key, val in caches.items():
                val = {str(k).lower(): v for k, v in val.items()} if isinstance(val, dict) else {}
                if not val:
                    continue
                if key not in cache_config.caches:
                    options = val.get('options') or {}
                    cache_config.add_cache(service, alias=key, cache=Cache(
                        engine=val.get('backend'),
                        host=val.get('host'),
                        port=val.get('port'),
                        options=val.get('options'),
                        timeout=val.get('timeout'),
                        location=val.get('location'),
                        prefix=val.get('key_prefix'),
                        max_entries=val.get('max_entries') or options.get('MAX_ENTRIES'),
                        key_function=val.get('key_function')
                    ))

        db_changed = False
        cached_changed = False

        from utilmeta.core.orm.backends.django.database import DjangoDatabaseAdaptor
        for name, db in db_config.databases.items():
            if not db.sync_adaptor_cls:
                db.sync_adaptor_cls = DjangoDatabaseAdaptor
            if name not in databases:
                db_changed = True
                databases[name] = self.get_database(db, service)

        from utilmeta.core.cache.backends.django import DjangoCacheAdaptor
        for name, cache in cache_config.caches.items():
            if not cache.sync_adaptor_cls:
                cache.sync_adaptor_cls = DjangoCacheAdaptor
            if name not in caches:
                cached_changed = True
                caches[name] = self.get_cache(cache)

        if db_changed:
            self.change_settings('DATABASES', databases, force=True)
            from django.db import connections
            connections._settings = connections.settings = connections.configure_settings(None)

        if cached_changed:
            self.change_settings('CACHES', caches, force=True)

        hosts = list(self.allowed_hosts)
        if service.origin:
            from urllib.parse import urlparse
            hosts.append(urlparse(service.origin).hostname)

        self.merge_list_settings('MIDDLEWARE', self.middleware)
        self.merge_list_settings('ALLOWED_HOSTS', hosts)
        self.merge_list_settings('DATABASE_ROUTERS', self.database_routers)

        if self.append_slash:
            self.change_settings('APPEND_SLASH', self.append_slash, force=True)

        try:
            if not getattr(django_settings, 'SECRET_KEY', None):
                self.change_settings('SECRET_KEY', self.get_secret(service), force=False)
        except ImproperlyConfigured:
            self.change_settings('SECRET_KEY', self.get_secret(service), force=False)

        if service.production:
            # elsewhere we keep the original settings
            self.change_settings('DEBUG', False, force=True)
        else:
            if getattr(django_settings, 'DEBUG', None) is False:
                service.production = True

        time_config = Time.config()
        if time_config:
            for key, val in self.get_time(time_config).items():
                self.change_settings(key, val)
        else:
            # the default django DATETIME_FORMAT is N j, Y, P
            # which is not a valid datetime string
            service.use(Time(
                time_zone=getattr(django_settings, 'TIME_ZONE', None),
                use_tz=getattr(django_settings, 'USE_TZ', True),
                # date_format=getattr(django_settings, 'DATE_FORMAT', Time.DATE_DEFAULT),
                # datetime_format=getattr(django_settings, 'DATETIME_FORMAT', Time.DATETIME_DEFAULT),
                # time_format=getattr(django_settings, 'TIME_FORMAT', Time.TIME_DEFAULT),
            ))

        # set DEFAULT_AUTO_FIELD before a (probably) apps reload
        self.change_settings('DEFAULT_AUTO_FIELD',
                             self.default_autofield or DEFAULT_AUTO_FIELD, force=True)
        if self.language:
            self.change_settings('LANGUAGE_CODE', self.language, force=True)
        if self.use_i18n:
            self.change_settings('USE_I18N', self.use_i18n, force=True)

        if self.apps:
            new_apps = self.merge_list_settings('INSTALLED_APPS', self.apps)
            from django.apps import apps
            if apps.ready:
                # apps already setup
                apps.ready = False
                apps.loading = False
                apps.populate(new_apps)

        if self._plugin_settings:
            for key, val in self._plugin_settings.items():
                if not hasattr(django_settings, key):
                    setattr(django_settings, key, val)

        if isinstance(self._extra_settings, dict):
            for key, val in self._extra_settings.items():
                if not hasattr(django_settings, key):
                    setattr(django_settings, key, val)

        module_name = os.environ.get(SETTINGS_MODULE)
        if module_name:
            self.module_name = module_name
            self.module = sys.modules[self.module_name]
        else:
            self.module_name = service.module_name
            self.module = service.module
            os.environ[SETTINGS_MODULE] = self.module_name

        self.wsgi_application = (getattr(django_settings, WSGI_APPLICATION, None) or
                                 self.wsgi_application or self.get_service_wsgi_app(service))
        self.root_urlconf = getattr(django_settings, ROOT_URLCONF, None) or self.root_urlconf
        if self.root_urlconf:
            self.url_conf = sys.modules.get(self.root_urlconf) or import_obj(self.root_urlconf)
        else:
            # raise ValueError(f'Invalid root urlconf: {self.root_urlconf}')
            self.root_urlconf = service.module_name or self.module_name
            self.url_conf = service.module or self.module

        self.change_settings(WSGI_APPLICATION, self.wsgi_application, force=False)
        self.change_settings(ROOT_URLCONF, self.root_urlconf, force=False)

        django.setup(set_prefix=False)
        self._setup = True

    def change_settings(self, settings_name, value, force=False):
        try:
            if not force and hasattr(self.django_settings, settings_name):
                return
            if (hasattr(self.django_settings, settings_name) and
                    getattr(self.django_settings, settings_name) != value):
                pass
            else:
                return
        except ImproperlyConfigured:
            pass
        setattr(self.django_settings, settings_name, value)
        from django.core.signals import setting_changed
        setting_changed.send(
            sender=self.__class__,
            setting=settings_name,
            value=value,
            enter=False,
        )

    def merge_list_settings(self, settings_name: str, settings_list: list):
        if not settings_list or not settings_name or not self.django_settings:
            return
        settings = getattr(self.django_settings, settings_name, [])
        if not multi(settings):
            settings = []
        else:
            settings = list(settings)
        new_values = []
        for value in settings_list:
            if value not in settings:
                settings.append(value)
                new_values.append(value)
        if new_values:
            self.change_settings(settings_name, settings, force=True)
        return new_values

    @classmethod
    def get_service_wsgi_app(cls, service: UtilMeta):
        app = service.meta_config.get('app')
        if not app:
            return f'{service.module_name}.app'
        return str(app).replace(':', '.')

    def setup(self, service: UtilMeta):
        # django_settings = None
        # reset_module = False
        module_name = os.environ.get(SETTINGS_MODULE)
        try:
            from django.conf import settings
            _ = settings.INSTALLED_APPS
            # if the settings is not configured, this will trigger ImproperlyConfigured
        except (ImportError, ImproperlyConfigured):
            pass
        else:
            self.django_settings = settings
            if self._setup:
                # already configured
                return
            # if apps:
            # django_settings = settings
            # this is a django application with settings configured
            # or a UtilMeta service with django settings and setup before Operations setup
            if _:
                return self.apply_settings(service, settings)
            # if apps is not set
            # this is probably the default settings, we override it

        # from utilmeta.ops.config import Operations
        # ops_config = service.get_config(Operations)
        # if ops_config:
        #     ops_config.setup(service)
        #     return
        if module_name:
            self.module_name = module_name
        if self.module_name:
            module = sys.modules[self.module_name]
        else:
            module = service.module
            self.module_name = service.module_name

        self.module = module
        db_config = service.get_config(DatabaseConnections)
        cache_config = service.get_config(CacheConnections)
        databases = {}
        caches = {}

        if db_config:
            if db_config.databases and 'default' not in db_config.databases:
                # often: a no-db service add Operations()
                # we need to define a '__ops' db, but django will force us to
                # define a 'default' db
                db_config.add_database(service, 'default', database=Database(
                    name=os.path.join(service.project_dir, '__default_db'),
                    engine='sqlite3'
                ))

            from utilmeta.core.orm.backends.django.database import DjangoDatabaseAdaptor
            for name, db in db_config.databases.items():
                if not db.sync_adaptor_cls:
                    db.sync_adaptor_cls = DjangoDatabaseAdaptor
                databases[name] = self.get_database(db, service)

        if cache_config:
            from utilmeta.core.cache.backends.django import DjangoCacheAdaptor
            for name, cache in cache_config.caches.items():
                if not cache.sync_adaptor_cls:
                    cache.sync_adaptor_cls = DjangoCacheAdaptor
                caches[name] = self.get_cache(cache)

        middleware = list(self.middleware or DEFAULT_MIDDLEWARE)
        adaptor = service.adaptor
        from .adaptor import DjangoServerAdaptor
        if isinstance(adaptor, DjangoServerAdaptor):
            adaptor.settings = self
            middleware_func = adaptor.middleware_func
            if middleware_func:
                setattr(self.module, middleware_func.__name__, middleware_func)
                middleware.append(f'{self.module_name}.{middleware_func.__name__}')

        hosts = list(self.allowed_hosts)
        if service.origin:
            from urllib.parse import urlparse
            hosts.append(urlparse(service.origin).hostname)
        self.wsgi_application = self.wsgi_application or self.get_service_wsgi_app(service)
        settings = {
            'DEBUG': not service.production,
            'SECRET_KEY': self.get_secret(service),
            'BASE_DIR': service.project_dir,
            'MIDDLEWARE': middleware,
            'INSTALLED_APPS': self.apps,
            'ALLOWED_HOSTS': hosts,
            'DATABASE_ROUTERS': self.database_routers,
            'APPEND_SLASH': self.append_slash,
            'LANGUAGE_CODE': self.language,
            'USE_I18N': self.use_i18n,
            'DEFAULT_AUTO_FIELD': self.default_autofield or DEFAULT_AUTO_FIELD,
            # 'DATABASES': databases,
            # 'CACHES': caches,
            ROOT_URLCONF: self.root_urlconf or service.module_name,
            WSGI_APPLICATION: self.wsgi_application
        }

        if databases:
            settings.update({'DATABASES': databases})
        if caches:
            settings.update({'CACHES': caches})

        time_config = Time.config()
        if time_config:
            settings.update(self.get_time(time_config))
        else:
            # mandatory
            settings.update({
                'TIME_ZONE': DEFAULT_TIME_ZONE,
                'USE_TZ': True,
            })

        if self._plugin_settings:
            settings.update(self._plugin_settings)
        if isinstance(self._extra_settings, dict):
            settings.update(self._extra_settings)

        self._settings = settings
        for attr, value in settings.items():
            setattr(module, attr, value)
            if self.django_settings is not None:
                self.change_settings(attr, value, force=True)
                # setattr(self.django_settings, attr, value)

        os.environ[SETTINGS_MODULE] = self.module_name or service.module_name
        # not using setdefault to prevent IDE set the wrong value by default
        django.setup(set_prefix=False)
        self._setup = True

        # import root url conf after the django setup
        if self.root_urlconf:
            self.url_conf = sys.modules.get(self.root_urlconf) or import_obj(self.root_urlconf)
        else:
            self.url_conf = service.module

        urlpatterns = getattr(self.url_conf, 'urlpatterns', [])
        # if self.urlpatterns:
        #     urlpatterns = urlpatterns + self.urlpatterns
        setattr(self.url_conf, 'urlpatterns', urlpatterns or [])
        # this set is required, otherwise url_conf.urlpatterns is not exists

        try:
            from django.conf import settings
        except (ImportError, ImproperlyConfigured) as e:
            raise ImproperlyConfigured(f'DjangoSettings: configure django failed: {e}') from e
        else:
            self.django_settings = settings

    @property
    def wsgi_module_ref(self):
        wsgi_app_ref = self.wsgi_application
        if not wsgi_app_ref:
            return None
        if ':' in wsgi_app_ref:
            return wsgi_app_ref.split(':')[0]
        return '.'.join(wsgi_app_ref.split('.')[:-1])

    @property
    def wsgi_app_attr(self):
        wsgi_app_ref = self.wsgi_application
        if isinstance(wsgi_app_ref, str) and '.' in wsgi_app_ref:
            return wsgi_app_ref.split('.')[-1]
        return None

    @property
    def wsgi_module(self):
        wsgi_module_ref = self.wsgi_module_ref
        if wsgi_module_ref:
            # if module_ref == self.module_name:
            #     return self.module
            try:
                return import_obj(wsgi_module_ref)
            except (ModuleNotFoundError, ImportError):
                return None
        return None

    @property
    def wsgi_app(self):
        wsgi_app_ref = self.wsgi_application
        if wsgi_app_ref:
            try:
                return import_obj(wsgi_app_ref)
            except (ModuleNotFoundError, ImportError):
                return None
        return None
