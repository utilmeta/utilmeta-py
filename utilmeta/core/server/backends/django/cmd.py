import datetime

from utilmeta.bin.commands.base import BaseServiceCommand
from utilmeta.bin.base import command, Arg
import os
from utilmeta.utils import write_to, SEG
from utilmeta.core.orm import DatabaseConnections
from utilmeta.bin.constant import INIT_FILE, RED, BLUE
from django.core.management import execute_from_command_line
from .settings import DjangoSettings


initial_file = "0001_initial"


class DjangoCommand(BaseServiceCommand):
    name = "django"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = self.service.get_config(DjangoSettings)
        # self.settings.setup(self.service)
        self.service.setup()  # setup here

    @command
    def add(self, name: str):
        """
        add an django application named <name> to this service, if your service specify an <apps_dir> in config,
        new application packages will create at there, elsewhere will create at current directory
        """
        path = self.settings.apps_path or self.cwd
        app = os.path.join(path, name)
        migrations = os.path.join(app, "migrations")
        init = os.path.join(app, INIT_FILE)
        m_init = os.path.join(migrations, INIT_FILE)
        api = os.path.join(app, "api.py")
        models = os.path.join(app, "models.py")
        schema = os.path.join(app, "schema.py")
        if os.path.exists(app):
            print(
                RED
                % f"meta Error: target application directory: {app} is already exists"
            )
            exit(1)

        os.makedirs(migrations)
        write_to(m_init, content="")
        write_to(init, content="")
        write_to(api, content="from utilmeta.core import api, orm, request, response\n")
        write_to(models, content="from django.db import models\n")
        write_to(schema, content="import utype\nfrom utilmeta.core import orm")

        print(
            f"meta: django application: <{BLUE % name}> successfully added to path: {app}"
        )

    @command
    def makemigrations(
        self, app_label: str = None, all: bool = Arg("--all", "-a", default=False)
    ):
        """
        execute django makemigrations command to generate migrations files
        """
        if app_label == "*":
            all = True
        args = ["meta", "makemigrations"]
        execute_from_command_line(args)
        if all:
            for app in self.settings.app_labels():
                db = self.settings.get_db(app)
                for d in db.dbs:
                    # include master and replicas
                    if d.alias == "default":
                        continue
                    execute_from_command_line([*args, app, f"--database={d.alias}"])
            return

    @command
    def fixmigrations(
        self, app_name: str, database: str = Arg("--database", default=None)
    ):
        # if the db's stage is not corresponding to the django_migration
        from django.apps.registry import apps, AppConfig

        dbs = self.service.get_config(DatabaseConnections)
        for alias, db in dbs.items():
            if database and database != alias:
                continue
            # migration = MigrationRecorder.Migration.objects.using(alias).filter(app=app_name)
            from django.db.migrations.executor import MigrationExecutor
            from django.db import connections
            from django.db import DatabaseError

            conn = connections[alias]
            executor = MigrationExecutor(conn)
            targets = sorted(
                [key[1] for key in executor.loader.graph.nodes if key[0] == app_name]
            )

            created_migrations = []
            try:
                # 1. if the migrated migration is not recorded
                migrated = 0
                for i, target in enumerate(targets):
                    try:
                        if not executor.recorder.migration_qs.filter(
                            app=app_name, name=target
                        ).exists():
                            migrated += 1
                            print(
                                f"[{app_name}] migrating {repr(target)} at database [{repr(alias)}]"
                            )
                            # target_executor = MigrationExecutor(conn)
                            target_executor = MigrationExecutor(conn)
                            # reload from db
                            plan = target_executor.migration_plan([(app_name, target)])
                            if not plan:
                                return
                            target_executor.migrate(targets, plan)
                            print(
                                f"[{app_name} migrating {repr(target)} completed at database [{repr(alias)}]"
                            )
                    except DatabaseError as e:
                        print(
                            f"[{app_name}] migrate unrecorded migration: {repr(target)} "
                            f"failed with error: {e}, save migration to [{repr(alias)}] and skip to next"
                        )
                        # close and reconnect database (or migration won't be saved)
                        conn.close()
                        conn.connect()
                        created_migrations.append(
                            executor.recorder.migration_qs.create(
                                name=target,
                                app=app_name,
                            )
                        )
                        if i == len(targets) - 1:
                            cfg: AppConfig = apps.get_app_config(app_name)
                            print("testing schemas of all models...")
                            for model in cfg.get_models():
                                try:
                                    _ = model.objects.values()[:1]
                                except DatabaseError as _e:
                                    print(f"model: {model} load failed: {_e}")
                                    raise e
                            print(
                                f"all missing migrations recorded: {created_migrations}"
                            )
                            break
                            # if all models is ok, we stop trying

                if not migrated:
                    print(
                        f"[{app_name}] migrations is clean at database [{repr(alias)}]"
                    )
                    # 2. if the recorded migration is not migrated
            except Exception as e:
                print(
                    f"[{app_name}] fix migrations at database: {repr(alias)} failed: {repr(e)}]"
                )
                if created_migrations:
                    print(f"[{app_name}] deleting created migrations")
                    for migration in created_migrations:
                        try:
                            migration.delete()
                        except DatabaseError:
                            pass

    @command
    def mergemigrations(self, app_name: str):
        """
        merge all migrations files to minimum for django apps
        """
        from django.apps.registry import apps, AppConfig

        dbs = self.service.get_config(DatabaseConnections)

        if app_name == "*" or app_name == "__all__":
            print("merge all apps:")
            # for key, cfg in apps.app_configs.items():
            #     cfg: AppConfig
            #     self.mergemigrations(cfg.label)
            for key, cfg in apps.app_configs.items():
                if not cfg.path.startswith(self.service.project_dir):
                    # eg. django content types / utilmeta.ops
                    continue
                cfg: AppConfig
                # if cfg.label == app_name:
                migrations_path = os.path.join(cfg.path, "migrations")
                files = next(os.walk(migrations_path))[2]
                for file in files:
                    if file.startswith(SEG):
                        continue
                    os.remove(os.path.join(migrations_path, file))

            for alias, db in dbs.items():
                from django.db import connections

                with connections[alias].cursor() as cursor:
                    cursor.execute("DELETE FROM django_migrations WHERE name != ''")

            execute_from_command_line(["meta", "makemigrations"])
            print(f"migrations for all app has merged")

            for key, cfg in apps.app_configs.items():
                cfg: AppConfig
                # if cfg.label == app_name:
                migrations_path = os.path.join(cfg.path, "migrations")
                files = next(os.walk(migrations_path))[2]
                for file in files:
                    if file.startswith(SEG):
                        continue
                    file_name = str(file).rstrip(".py")

                    for alias, db in dbs.items():
                        from django.db import connections

                        with connections[alias].cursor() as cursor:
                            cursor.execute(
                                "INSERT INTO django_migrations "
                                "(app, name, applied) values ('%s', '%s', '%s')"
                                % (cfg.label, file_name, str(datetime.datetime.now()))
                            )

                    # os.remove(os.path.join(migrations_path, file))

            return

        print("merging for app:", app_name)

        for alias, db in dbs.items():
            from django.db import connections

            with connections[alias].cursor() as cursor:
                cursor.execute(
                    "DELETE FROM django_migrations WHERE app='%s' and name != '%s'"  # noqa
                    % (app_name, initial_file)
                )

        for key, cfg in apps.app_configs.items():
            cfg: AppConfig
            if cfg.label == app_name:
                migrations_path = os.path.join(cfg.path, "migrations")
                files = next(os.walk(migrations_path))[2]
                for file in files:
                    if file.startswith(SEG):
                        continue
                    os.remove(os.path.join(migrations_path, file))

        execute_from_command_line(["meta", "makemigrations"])
        print(f"migrations for app: <{app_name}> has merged")

    # @property
    # def exec_args(self):
    #     return ['meta', *self.argv]

    def fallback(self):
        import sys

        execute_from_command_line(sys.argv)
