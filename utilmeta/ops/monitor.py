import platform
import psutil
import os
import time

import utype

from utilmeta.utils import get_max_open_files, get_max_socket_conn, get_mac_address, get_sql_info, \
    get_sys_net_connections_info, get_system_fds, get_system_open_files, get_server_ip, DB, ignore_errors
from .schema import ServerSchema
from .models import DatabaseConnection
from utilmeta.core.orm import DatabaseConnections
from utilmeta.core.cache import CacheConnections, Cache
from typing import Optional, Tuple
import sys


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


def get_redis_info(cache: Cache) -> dict:
    try:
        from redis import Redis
    except ModuleNotFoundError:
        return {}
    from redis.exceptions import ConnectionError
    try:
        con = Redis.from_url(cache.get_location())
        return dict(con.info())
    except ConnectionError:
        return {}


@ignore_errors(default=0)
def get_cache_size(using: str) -> int:
    cache = CacheConnections.get(using)
    if not cache:
        return 0
    if cache.type == 'db':
        return get_db_size(using)
    elif cache.type == 'file':
        loc = cache.location
        return os.path.getsize(loc)
    elif cache.type == 'redis':
        info = get_redis_info(cache)
        return info.get('used_memory', 0)
    elif cache.type == 'memcached':
        if sys.platform == 'linux':
            # echo only apply to unix systems
            try:
                host, port = cache.location.split(':')
                cmd = "echo \'stats\' | nc - w 1 %s %s | awk \'$2 == \"bytes\" { print $3 }\'" % (host, port)
                res = os.popen(cmd).read()
                return int(res)
            except (OSError, TypeError):
                return 0
    return 0


class CacheStatus(utype.Schema):
    pid: int = utype.Field(alias_from=['process_id'], default=None, no_output=True)
    used_memory: int = utype.Field(alias_from=['limit_maxbytes'], default=None)
    current_connections: int = utype.Field(alias_from=['connected_clients', 'curr_connections'], default=None)
    total_connections: int = utype.Field(alias_from=['total_connections_received'], default=None)
    qps: float = utype.Field(alias_from=['instantaneous_ops_per_sec'], default=None)


@ignore_errors(default=None)
def get_cache_stats(using: str) -> Optional[CacheStatus]:
    cache = CacheConnections.get(using)
    if not cache:
        return None
    if cache.type == 'redis':
        return CacheStatus(get_redis_info(cache))
    elif cache.type == 'memcached':
        from pymemcache.client.base import Client
        mc = Client(cache.get_location())
        return CacheStatus(mc.stats())
    return None


@ignore_errors(default=list)
def get_db_connections(using: str):
    db_sql = {
        DB.PostgreSQL: "select pid, usename, client_addr, client_port, state," # noqa
                       " backend_start, query_start, state_change, xact_start, wait_event, query" # noqa
                       " from pg_stat_activity WHERE datname = '%s';", # noqa
        DB.MySQL: "select * from information_schema.processlist where db = '%s';",  # noqa
        DB.Oracle: "select status from v$session where username='%s';"  # noqa
    }
    db = DatabaseConnections.get(using)
    if db.type not in db_sql:
        return []
    from django.db import connections
    with connections[db.alias].cursor() as cursor:
        db_type: str = str(cursor.db.display_name).lower()
        if db_type not in db_sql:
            return []
        db_name: str = db.name
        if db_type == DB.Oracle:
            db_name = db.user
        cursor.execute(db_sql[db_type] % db_name)
        result = cursor.fetchall()
        values = []
        if db.type == DB.PostgreSQL:
            for pid, usename, client_addr, client_port, state, \
                    backend_start, query_start, state_change, xact_start, wait_event, query in result:
                if usename != db.user:
                    continue
                if not pid or not usename or not client_addr or not client_port or not state or not query:
                    continue
                # find = False
                # for conn in current_connections:
                #     if str(conn.get('pid')) == str(pid):    # noqa, strange behaviour for AttributeError
                #         values.append(conn)
                #         find = True
                #         break
                # if find:
                #     continue
                operation, tables = get_sql_info(query)
                if not operation:
                    continue
                values.append(DatabaseConnection(
                    status=state,
                    active=state == 'active',
                    client_addr=client_addr,
                    client_port=client_port,
                    pid=pid,
                    backend_start=backend_start,
                    query_start=query_start,
                    state_change=state_change,
                    wait_event=wait_event,
                    transaction_start=xact_start,
                    query=query,
                    operation=operation,
                    tables=tables
                ))
        return values


@ignore_errors(default=0)
def get_db_server_connections(using: str):
    db_sql = {
        DB.PostgreSQL: "select count(*) from pg_stat_activity", # noqa
        DB.MySQL: "select count(*) from information_schema.processlist", # noqa
        DB.Oracle: "select count(*) from v$session" # noqa
    }
    db = DatabaseConnections.get(using)
    if db.type not in db_sql:
        return []
    from django.db import connections
    with connections[db.alias].cursor() as cursor:
        db_type: str = str(cursor.db.display_name).lower()
        cursor.execute(db_sql[db_type])
        return int(cursor.fetchone()[0])


@ignore_errors(default=0)
def get_db_connections_num(using: str) -> Tuple[Optional[int], Optional[int]]:
    from django.db import connections
    db = DatabaseConnections.get(using)
    if not db:
        return None, None
    db_sql = {
        DB.PostgreSQL: "select state from pg_stat_activity WHERE datname = '%s';", # noqa
        DB.MySQL: "select command from information_schema.processlist where db = '%s';", # noqa
        DB.Oracle: "select status from v$session where username='%s';" # noqa
    }
    if db.type not in db_sql:
        return None, None
    with connections[using].cursor() as cursor:
        db_type: str = str(cursor.db.display_name).lower()
        db_name: str = db.name
        if db_type == DB.Oracle:
            db_name = db.user
        cursor.execute(db_sql[db_type] % db_name)
        status = [str(result[0]).lower() for result in cursor.fetchall()]
        # for MySQL, command=Query means active, for others, state/status = active means active
        active_count = len([s for s in status if s in ('active', 'query')])
        conn_count = len(status)
        return conn_count, active_count


@ignore_errors(default=None)
def get_db_size(using: str) -> int:
    from django.db import connections
    db_sql = {
        DB.PostgreSQL: "select pg_database_size('%s');",
        DB.MySQL: "select sum(DATA_LENGTH)+sum(INDEX_LENGTH) " # noqa
                  "from information_schema.tables where table_schema='%s';", # noqa
        DB.Oracle: "select sum(bytes) from dba_segments where owner='%s'" # noqa
    }
    db = DatabaseConnections.get(using)
    if db.is_sqlite:
        return os.path.getsize(db.name)
    with connections[using].cursor() as cursor:
        db_type: str = str(cursor.db.display_name).lower()
        if db_type not in db_sql:
            return 0
        db_name: str = db.name
        if db_type == DB.Oracle:
            db_name = f'{db.user}/{db.name}'
        cursor.execute(db_sql[db_type] % db_name)
        return int(cursor.fetchone()[0])


@ignore_errors(default=None)
def get_db_server_size(using: str) -> int:
    from django.db import connections
    db_sql = {
        DB.PostgreSQL: "select sum(pg_database_size(pg_database.datname)) from pg_database;", # noqa
        DB.MySQL: "select sum(DATA_LENGTH)+sum(INDEX_LENGTH) from information_schema.tables;", # noqa
        DB.Oracle: "select sum(bytes) from dba_segments;" # noqa
    }
    db = DatabaseConnections.get(using)
    if db.is_sqlite:
        return os.path.getsize(db.name)
    with connections[using].cursor() as cursor:
        db_type: str = str(cursor.db.display_name).lower()
        if db_type not in db_sql:
            return 0
        cursor.execute(db_sql[db_type])
        return int(cursor.fetchone()[0])


@ignore_errors(default=None)
def get_db_max_connections(using: str) -> int:
    from django.db import connections
    db_sql = {
        DB.PostgreSQL: "SHOW max_connections;",
        DB.MySQL: 'SHOW VARIABLES LIKE "max_connections";'
    }
    with connections[using].cursor() as cursor:
        db_type: str = str(cursor.db.display_name).lower()
        if db_type not in db_sql:
            return 0
        cursor.execute(db_sql[db_type])
        return int(cursor.fetchone()[0])


@ignore_errors(default=None)
def get_db_transactions(using: str) -> int:
    from django.db import connections
    db_sql = {
        DB.PostgreSQL: "select xact_commit from pg_stat_database where datname='%s';", # noqa
    }
    db = DatabaseConnections.get(using)
    with connections[using].cursor() as cursor:
        db_type: str = str(cursor.db.display_name).lower()
        if db_type not in db_sql:
            return 0
        cursor.execute(db_sql[db_type] % db.name)
        return int(cursor.fetchone()[0])
