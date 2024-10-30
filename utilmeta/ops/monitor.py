import platform
import psutil
import os
import time
from utilmeta.utils import get_max_open_files, get_max_socket_conn, get_mac_address,\
    get_sys_net_connections_info, get_system_fds, get_system_open_files, get_server_ip
from .schema import ServerSchema


def get_current_server(unit: int = 1024 ** 2) -> ServerSchema:
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(os.getcwd())
    devices = {}

    def get_num(n):
        return round(n / unit) * unit

    for device in psutil.disk_partitions():
        if 'loop' in device.device:
            continue
        try:
            disk_usage = psutil.disk_usage(device.mountpoint)
        except PermissionError:
            continue
        devices[device.device] = dict(
            mountpoint=device.mountpoint,
            fstype=device.fstype,
            opts=device.opts,
            total=get_num(disk_usage.total),
            # used=disk_usage.used
        )

    return ServerSchema(
        ip=get_server_ip(),
        mac=get_mac_address(),
        cpu_num=os.cpu_count(),
        memory_total=get_num(mem.total),
        disk_total=get_num(disk.total),
        utcoffset=-time.timezone,
        hostname=platform.node(),
        system=str(platform.system()).lower(),
        devices=devices,
        max_open_files=get_max_open_files(),
        max_socket_conn=get_max_socket_conn(),
        platform=dict(
            platform=platform.platform(),
            version=platform.version(),
            release=platform.release(),
            machine=platform.machine(),
            processor=platform.processor(),
            bits=platform.architecture()[0]
        )
    )


def get_sys_metrics(cpu_interval: float = None, with_open_files: bool = True):
    from utilmeta.ops.schema import SystemMetricsMixin
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(os.getcwd())
    total, active, info = get_sys_net_connections_info()
    cpu_percent = psutil.cpu_percent(interval=cpu_interval)
    open_files = get_system_open_files() if with_open_files else None
    fds = get_system_fds()
    return SystemMetricsMixin(
        cpu_percent=cpu_percent,
        used_memory=mem.used,
        memory_percent=100 * mem.used / mem.total,
        disk_percent=100 * disk.used / disk.total,
        file_descriptors=fds,
        open_files=open_files,
        active_net_connections=active,
        total_net_connections=total,
        net_connections_info=info
    )


#
# def get_db_connections(db: Database, current_connections: List[DatabaseConnectionSchema]):
#     db_sql = {
#         DB.PostgreSQL: "select pid, usename, client_addr, client_port, state," # noqa
#                        " backend_start, query_start, state_change, xact_start, wait_event, query" # noqa
#                        " from pg_stat_activity WHERE datname = '%s';", # noqa
#         DB.MySQL: "select * from information_schema.processlist where db = '%s';",  # noqa
#         DB.Oracle: "select status from v$session where username='%s';"  # noqa
#     }
#     if db.type not in db_sql:
#         return []
#     from django.db import connections
#     with connections[db.alias].cursor() as cursor:
#         db_type: str = str(cursor.db.display_name).lower()
#         db_name: str = db.name
#         if db_type == DB.Oracle:
#             db_name = db.user
#         cursor.execute(db_sql[db_type] % db_name)
#         result = cursor.fetchall()
#         values = []
#         if db.type == DB.PostgreSQL:
#             for pid, usename, client_addr, client_port, state,\
#                     backend_start, query_start, state_change, xact_start, wait_event, query in result:
#                 if usename != db.user:
#                     continue
#                 if not pid or not usename or not client_addr or not client_port or not state or not query:
#                     continue
#                 find = False
#                 for conn in current_connections:
#                     if str(conn.get('pid')) == str(pid):    # noqa, strange behaviour for AttributeError
#                         values.append(conn)
#                         find = True
#                         break
#                 if find:
#                     continue
#                 operation, tables = get_sql_info(query)
#                 if not operation:
#                     continue
#                 values.append(DatabaseConnectionSchema(
#                     status=state,
#                     active=state == 'active',
#                     client_addr=client_addr,
#                     client_port=client_port,
#                     pid=pid,
#                     backend_start=backend_start,
#                     query_start=query_start,
#                     state_change=state_change,
#                     wait_event=wait_event,
#                     transaction_start=xact_start,
#                     query=query,
#                     operation=operation,
#                     tables=tables
#                 ))
#         return values
#
#
# def get_db_server_connections(db: Database):
#     db_sql = {
#         DB.PostgreSQL: "select count(*) from pg_stat_activity", # noqa
#         DB.MySQL: "select count(*) from information_schema.processlist", # noqa
#         DB.Oracle: "select count(*) from v$session" # noqa
#     }
#     if db.type not in db_sql:
#         return []
#     from django.db import connections
#     with connections[db.alias].cursor() as cursor:
#         db_type: str = str(cursor.db.display_name).lower()
#         cursor.execute(db_sql[db_type])
#         return int(cursor.fetchone()[0])
#
#
# def get_db_connections_num(using: str) -> Tuple[Optional[int], Optional[int]]:
#     from django.db import connections
#     from utilmeta.conf import config
#     db = config.databases.get(using)
#     if not db:
#         return None, None
#     db_sql = {
#         DB.PostgreSQL: "select state from pg_stat_activity WHERE datname = '%s';", # noqa
#         DB.MySQL: "select command from information_schema.processlist where db = '%s';", # noqa
#         DB.Oracle: "select status from v$session where username='%s';" # noqa
#     }
#     if db.type not in db_sql:
#         return None, None
#     with connections[using].cursor() as cursor:
#         db_type: str = str(cursor.db.display_name).lower()
#         db_name: str = db.name
#         if db_type == DB.Oracle:
#             db_name = db.user
#         cursor.execute(db_sql[db_type] % db_name)
#         status = [str(result[0]).lower() for result in cursor.fetchall()]
#         # for MySQL, command=Query means active, for others, state/status = active means active
#         active_count = len([s for s in status if s in ('active', 'query')])
#         conn_count = len(status)
#         return conn_count, active_count
#
#
# def clear_invalid_connections(using: str, timeout: int = 60,
#                               include_idle: bool = True, include_active: bool = False):
#     from django.db import connections
#     from utilmeta.conf import config
#     db = config.databases.get(using)
#     if not db:
#         return
#     db_sql = {
#         'postgres': """
# WITH inactive_connections AS (
#     SELECT
#         pid,
#         rank() over (partition by client_addr order by backend_start) as rank
#     FROM
#         pg_stat_activity
#     WHERE
#         -- Exclude the thread owned connection (ie no auto-kill)
#          pid <> pg_backend_pid()
#     AND
#         -- Exclude known applications connections
#         application_name !~ '(?:psql)|(?:pgAdmin.+)|(?:python)'
#     AND
#         -- Include connections to the same database the thread is connected to
#         datname = '%s'
#     AND
#         -- Include inactive connections only
#         state in (%s)
#     AND
#         -- Include old connections (found with the state_change field)
#         current_timestamp - state_change > interval '%s seconds'
# )
# SELECT
#     pg_terminate_backend(pid)
# FROM
#     inactive_connections
# WHERE
#     rank > 1
#         """
#     }
#     sql = db_sql.get(db.type)
#     if not sql:
#         return
#     states = []
#     if include_active:
#         states.append('active')
#     if include_idle:
#         states.extend(['idle', 'idle in transaction', 'idle in transaction (aborted)', 'disabled'])
#     state = ', '.join([repr(s) for s in states])
#     with connections[using].cursor() as cursor:
#         cursor.execute(sql % (db.name, state, timeout))
#
#
# def get_db_size(using: str) -> int:
#     from django.db import connections
#     from utilmeta.conf import config
#     db_sql = {
#         DB.PostgreSQL: "select pg_database_size('%s');",
#         DB.MySQL: "select sum(DATA_LENGTH)+sum(INDEX_LENGTH) " # noqa
#                   "from information_schema.tables where table_schema='%s';", # noqa
#         DB.Oracle: "select sum(bytes) from dba_segments where owner='%s'" # noqa
#     }
#     db = config.databases[using]
#     with connections[using].cursor() as cursor:
#         db_type: str = str(cursor.db.display_name).lower()
#         if db_type == DB.SQLite:
#             file = db.file
#             return os.path.getsize(file)
#         if db_type not in db_sql:
#             return 0
#         db_name: str = db.name
#         if db_type == DB.Oracle:
#             db_name = f'{db.user}/{db.name}'
#         cursor.execute(db_sql[db_type] % db_name)
#         return int(cursor.fetchone()[0])
#
#
# def get_db_server_size(using: str) -> int:
#     from django.db import connections
#     from utilmeta.conf import config
#     db_sql = {
#         DB.PostgreSQL: "select sum(pg_database_size(pg_database.datname)) from pg_database;", # noqa
#         DB.MySQL: "select sum(DATA_LENGTH)+sum(INDEX_LENGTH) from information_schema.tables;", # noqa
#         DB.Oracle: "select sum(bytes) from dba_segments;" # noqa
#     }
#     db = config.databases[using]
#     with connections[using].cursor() as cursor:
#         db_type: str = str(cursor.db.display_name).lower()
#         if db_type == DB.SQLite:
#             file = db.file
#             return os.path.getsize(file)
#         if db_type not in db_sql:
#             return 0
#         cursor.execute(db_sql[db_type])
#         return int(cursor.fetchone()[0])
#
#
# def get_db_max_connections(using: str) -> int:
#     from django.db import connections
#     db_sql = {
#         DB.PostgreSQL: "SHOW max_connections;",
#         DB.MySQL: 'SHOW VARIABLES LIKE "max_connections";'
#     }
#     with connections[using].cursor() as cursor:
#         db_type: str = str(cursor.db.display_name).lower()
#         if db_type not in db_sql:
#             return 0
#         cursor.execute(db_sql[db_type])
#         return int(cursor.fetchone()[0])
#
#
# def get_db_transactions(using: str) -> int:
#     from django.db import connections
#     db_sql = {
#         DB.PostgreSQL: "select xact_commit from pg_stat_database where datname='%s';", # noqa
#     }
#     with connections[using].cursor() as cursor:
#         db_type: str = str(cursor.db.display_name).lower()
#         db = config.databases[using]
#         if db_type not in db_sql:
#             return 0
#         cursor.execute(db_sql[db_type] % db.name)
#         return int(cursor.fetchone()[0])
#
#
# def database_monitor():
#     from utilmeta.util.alert import Alert
#     db = config.databases.get(val.alias)
#     if not db:
#         return
#
#     connected = val.connected
#     err = None
#     try:
#         val.used_space = self.get_db_size(db.alias)
#         val.server_used_space = self.get_db_server_size(db.alias)
#         val.server_connections = self.get_db_server_connections(db)
#         val.server_connections_limit = self.get_db_max_connections(db.alias)
#         val.connections = self.get_db_connections(db, val.connections)
#         transactions = self.get_db_transactions(db.alias)
#         val.new_transactions = max(0, transactions - val.transactions)
#         val.transactions = transactions
#         val.connected = True
#     except (exc.ProgrammingError, exc.OperationalError) as e:
#         # database failed
#         val.connected = False
#         err = e
#
#     if config.alert and connected != val.connected:
#         Alert.log(
#             level=config.alert.database_unavailable_alert_level,
#             category=AlertCategory.service_unavailable,
#             subcategory='database_unavailable',
#             name=f'Database instance: [{val.name}]({val.loc}) unavailable',
#             ident=f'database_unavailable:{val.loc}',
#             message=f'connect to database failed with error: {str(err)}',
#             trigger=not val.connected
#         )
#
#     if not val.connected:
#         # still need to store val.connected=False
#         return val
#
#     val.current_connections = len(val.connections)
#     val.active_connections = len([conn for conn in val.connections if conn.active])
#
#     # slow queries can also pick form database connection (based on query_start)
#     if db.clear_threshold and val.current_connections > db.clear_threshold:
#         self.log.info(f'start to clear db connections for '
#                       f'current_connections({val.current_connections}) > threshold({db.clear_threshold})')
#
#         if db.clear_active_connection_timeout:
#             self.clear_invalid_connections(
#                 using=val.alias, timeout=db.clear_active_connection_timeout,
#                 include_active=True, include_idle=False)
#         if db.clear_idle_connection_timeout:
#             self.clear_invalid_connections(
#                 using=val.alias, timeout=db.clear_idle_connection_timeout,
#                 include_active=False, include_idle=True)
#     else:
#         # regular clear
#         if db.active_connection_timeout:
#             self.clear_invalid_connections(
#                 using=val.alias, timeout=db.active_connection_timeout,
#                 include_active=True, include_idle=False)
#         if db.idle_connection_timeout:
#             self.clear_invalid_connections(
#                 using=val.alias, timeout=db.idle_connection_timeout,
#                 include_active=False, include_idle=True)
#
#     return val