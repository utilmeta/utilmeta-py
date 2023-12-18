import django
import os
import sys
from typing import Union, List
from utilmeta import UtilMeta
from utilmeta.utils import import_obj
from utilmeta.conf.base import Config
from utilmeta.conf.time import Time
from utilmeta.core.orm.databases import DatabaseConnections, Database

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
ROOT_URLCONF = "ROOT_URLCONF"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SETTINGS_MODULE = 'DJANGO_SETTINGS_MODULE'
DEFAULT_LANGUAGE_CODE = "en-us"
DEFAULT_TIME_ZONE = "UTC"
DEFAULT_USE_I18N = True
DEFAULT_USE_TZ = True


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
            allowed_hosts: list = (),
            middleware: Union[tuple, List[str]] = (),
            default_autofield: str = None,
            wsgi_application: str = None,
            # time_zone: str = None,
            # use_tz: bool = None,
            user_i18n: bool = None,
            language: str = None,
            append_slash: bool = False,
    ):
        super().__init__(**locals())
        self.module_name = module_name
        self.secret_key = secret_key
        self.apps_package = apps_package
        self.apps = apps
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
        self._settings = {}
        self._plugin_settings = {}

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
        tag = f'{service.project_dir}:{service.name}:{service.description}:{service.version}' \
              f'{service.backend_name}:{service.module_name}' \
              f'{django.__version__}{utilmeta.__version__}{sys.version}{platform.platform()}'.encode()
        return hashlib.sha256(tag).hexdigest()

    def load_apps(self):
        installed_apps = list(DEFAULT_APPS)
        if self.apps_package:
            # if self.apps_package == '.':
            #     installed_apps.append(self.module.__package__)
            # else:
            apps_path = self.apps_path
            hosted_labels = [p for p in next(os.walk(apps_path))[1] if '__' not in p]
            installed_apps.extend([f'{self.apps_package}.{app}' for app in hosted_labels])
        installed_apps.extend(self.apps)
        return installed_apps

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
            'OPTIONS': options
        }

    def hook(self, service: UtilMeta):
        from .cmd import DjangoCommand
        service.register_command(DjangoCommand)

    def setup(self, service: UtilMeta):
        if self._settings:
            # already configured
            return
        if self.module_name:
            module = sys.modules[self.module_name]
        else:
            module = service.module

        self.module = module
        config = service.get_config(DatabaseConnections)
        databases = {}

        if config:
            for name, db in config.databases.items():
                databases[name] = self.get_database(db, service)

        if self.root_urlconf:
            url_conf = sys.modules[self.root_urlconf]
        else:
            url_conf = service.module

        urlpatterns = getattr(url_conf, 'urlpatterns', None)
        if not urlpatterns:
            setattr(url_conf, 'urlpatterns', [])

        settings = {
            'DEBUG': not service.production,
            'SECRET_KEY': self.get_secret(service),
            'BASE_DIR': service.project_dir,
            'MIDDLEWARE': self.middleware or DEFAULT_MIDDLEWARE,
            'INSTALLED_APPS': self.load_apps(),
            'ALLOWED_HOSTS': self.allowed_hosts,
            # 'DATABASE_ROUTERS': self.routers,
            'APPEND_SLASH': self.append_slash,
            'LANGUAGE_CODE': self.language,
            'USE_I18N': self.use_i18n,
            'DEFAULT_AUTO_FIELD': self.default_autofield or DEFAULT_AUTO_FIELD,
            'DATABASES': databases,
            ROOT_URLCONF: self.root_urlconf or service.module_name,
            WSGI_APPLICATION: self.wsgi_application or f'{service.module_name}.app',
        }

        time_config = Time.config()
        if time_config:
            settings.update({
                'DATETIME_FORMAT': time_config.datetime_format,
                'DATE_FORMAT': time_config.date_format,
                'TIME_ZONE': time_config.time_zone,
                'USE_TZ': time_config.use_tz,
            })
        else:
            # mandatory
            settings.update({
                'TIME_ZONE': None,
                'USE_TZ': None,
            })

        if self._plugin_settings:
            settings.update(self._plugin_settings)

        self._settings = settings
        for attr, value in settings.items():
            setattr(module, attr, value)
        os.environ[SETTINGS_MODULE] = self.module_name or service.module_name
        # not using setdefault to prevent IDE set the wrong value by default
        django.setup(set_prefix=False)
