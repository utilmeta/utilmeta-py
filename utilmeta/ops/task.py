import os
import threading
from .config import Operations
from .log import setup_locals, batch_save_logs, worker_logger
from .monitor import get_sys_metrics
import psutil
from utilmeta.utils import time_now, replace_null, Error, normalize, ignore_errors
from datetime import timedelta, datetime, timezone
from django.db import models
from .aggregation import aggregate_logs, aggregate_endpoint_logs
from typing import Optional
import random
import time


# class LogRedirector:
#     """
#     Redirects stdout, warnings, and/or errors of the current thread to a specific file based on the level.
#     """
#     def __init__(self, file, level="info"):
#         self.file = open(file, "a") if isinstance(file, str) else file
#         self.level = level.lower() if isinstance(level, str) else None
#         self.original_stdout = sys.stdout
#         self.original_stderr = sys.stderr
#         self.original_showwarning = warnings.showwarning
#
#     def __enter__(self):
#         if not self.file:
#             return self
#         if self.level == "info":
#             sys.stdout = self.file
#             sys.stderr = self.file
#             warnings.showwarning = self._redirect_warning
#         elif self.level == "warn":
#             sys.stderr = self.file
#             warnings.showwarning = self._redirect_warning
#         elif self.level == "error":
#             sys.stderr = self.file
#         return self
#
#     def __exit__(self, exc_type, exc_value, traceback):
#         if not self.file:
#             return self
#         self.file.close()
#         if not self.level:
#             return
#         sys.stdout = self.original_stdout
#         sys.stderr = self.original_stderr
#         warnings.showwarning = self.original_showwarning
#         # thread_name = threading.current_thread().name
#         # print(f"[INFO] Stdout, warnings, and errors of thread '{thread_name}' are restored.")
#
#     def _redirect_warning(self, message, category, filename, lineno, file=None, line=None):
#         print(warnings.formatwarning(message, category, filename, lineno), file=self.file)


class BaseCycleTask:
    def __init__(self, interval: int, new_thread: bool = True):
        self.interval = interval
        self._stopped = False
        self._last_exec: Optional[datetime] = None
        self.new_thread = new_thread

        # fixme: using signal seems to cause tornado / starlette hangs
        # import signal
        # try:
        #     signal.signal(signal.SIGTERM, self.exit_gracefully)
        # except AttributeError:
        #     pass

    def __call__(self, *args, **kwargs):
        raise NotImplementedError

    def start(self):
        while not self._stopped:
            self._last_exec = time_now()
            if self.new_thread:
                thread = threading.Thread(target=self, daemon=True)
                thread.start()
                thread.join(timeout=self.interval)
            else:
                try:
                    if not self():
                        break
                except Exception as e:
                    self.handle_error(e)

            if self._stopped:
                break
            wait_for = max(
                0.0, self.interval - (time_now() - self._last_exec).total_seconds()
            )
            if wait_for:
                time.sleep(wait_for)

    def handle_error(self, e):
        err = Error(e)
        err.setup()
        print(err.full_info)

    def exit_gracefully(self, signum, frame):
        self.stop(wait=False)

    def stop(self, wait: bool = False):
        self._stopped = True


class OperationWorkerTask(BaseCycleTask):
    DISCONNECTED_WORKER_RETENTION = timedelta(hours=12)
    DISCONNECTED_INSTANCE_RETENTION = timedelta(days=3)
    DISCONNECTED_SERVER_RETENTION = timedelta(days=3)
    AGGREGATION_EXPIRE_TIME = [timedelta(days=7), timedelta(days=30)]

    LAYER_INTERVAL = [timedelta(hours=1), timedelta(days=1)]
    DEFAULT_CPU_INTERVAL = 1
    MAX_SYNC_RETRIES = 10
    UPDATE_BATCH_MAX_SIZE = 50
    REPORT_BATCH_MAX_SIZE = 50

    def __init__(self, config: Operations):
        self.config = config
        super().__init__(interval=self.config.worker_cycle)

        self.instance = None
        self.worker = None
        self.server = None
        self.supervisor = None

        from utilmeta import service

        self.service = service

        self.hourly_aggregation = None
        self.daily_aggregation = None

        self._init_cycle = False
        self._synced = False
        self._sync_retries = 0

    def __call__(self, *args, **kwargs):
        try:
            self.worker_cycle()
            return True
        finally:
            self.clear_connections()

    @classmethod
    def clear_connections(cls):
        # close all connections
        from django.db import connections
        connections.close_all()

    @property
    def node_id(self):
        return self.supervisor.node_id if self.supervisor else None

    def handle_error(self, e, type: str = 'ops.task'):
        err = Error(e)
        err.setup(
            with_cause=False,
            with_variables=False
        )
        self.log(str(e) + '\n' + err.full_info, level='error')
        print(err.full_info)

    def log(self, message: str, level: str = 'info'):
        return self.config.write_task_log(message, level=level)

    def warn(self, message: str):
        return self.log(message, 'warn')

    def worker_cycle(self):
        if not self._last_exec:
            self._last_exec = time_now()

        self.log("worker cycle")

        if not self._init_cycle:
            self.log("init ops migrate")
            self.config.migrate()
            # self.config.migrate()
            # 1. db not created
            # 2. db not updated to the current version

        setup_locals(self.config)

        # try to set up locals before
        from .log import _server, _worker, _instance, _supervisor

        self.worker = _worker
        self.server = _server
        self.instance = _instance
        self.supervisor = _supervisor

        try:
            # 1. save logs
            batch_save_logs()
        except Exception as e:
            self.handle_error(e, type='ops.task.log')

        try:
            # 2. update worker
            worker_logger.update_worker(
                record=not self.config.monitor.worker_disabled,
                interval=self.config.worker_cycle,
            )
            # update worker from every worker
            # to make sure that the connected workers has the primary role to execute the following
            self.update_workers()
        except Exception as e:
            self.warn(f"Update workers failed with error: {e}")

        if self._stopped:
            # if this worker is stopped
            # we exit right after collect all the memory-stored logs
            # other process (aka. the restarted process) will be take care of the rest
            self.log("worker cycle stopped")
            return

        if self.is_worker_primary:
            # Is this worker the primary worker of the current instance
            # detect the running worker with the minimum PID
            if not self._synced and self._sync_retries < self.MAX_SYNC_RETRIES:
                # 1st cycle
                manager = self.config.resources_manager_cls(self.service)
                try:
                    manager.init_service_resources(
                        self.supervisor, instance=self.instance
                    )
                    # ignore errors
                except Exception as e:
                    self.warn(f"sync resources failed with error: {e}")
                    self._sync_retries += 1
                else:
                    self._synced = True

            self.monitor()
            self.heartbeat()
            self.alert()
            self.aggregation()
            self.clear()

            self.log(f"worker cycle [primary] finished")

        self._init_cycle = True

    @property
    def connected_workers(self):
        from .models import Worker

        if not self.instance or not self.server:
            return Worker.objects.none()

        return Worker.objects.filter(
            instance=self.instance,
            server=self.server,
            connected=True,
        )

    def update_workers(self):
        from .models import Worker

        if not self.instance or not self.server:
            return

        disconnected = []
        for worker in self.connected_workers:
            if worker.pid == os.getpid():
                continue
            try:
                psutil.Process(worker.pid)
            except psutil.Error:
                disconnected.append(worker.pk)
                continue

        Worker.objects.filter(instance=self.instance).filter(
            models.Q(time__lte=time_now() - timedelta(seconds=self.interval * 2))
            | models.Q(pk__in=disconnected)
        ).update(connected=False)

    def get_total_memory(self):
        mem = 0
        try:
            for pss, uss in self.connected_workers.values_list(
                "memory_info__pss", "memory_info__uss"
            ):
                mem += pss or uss or 0
        except Exception:  # noqa
            # field error / Operational error
            # maybe sqlite, not support json lookup
            for mem_info in self.connected_workers.values_list(
                "memory_info", flat=True
            ):
                mem += mem_info.get("pss") or mem_info.get("uss") or 0
        return mem

    def get_instance_metrics(self):
        total = self.connected_workers.aggregate(
            outbound_requests=models.Sum("outbound_requests"),
            queries_num=models.Sum("queries_num"),
            requests=models.Sum("requests"),
        )
        avg_aggregates = {}
        if total["outbound_requests"]:
            avg_aggregates.update(
                outbound_avg_time=models.Sum(
                    models.F("outbound_avg_time") * models.F("outbound_requests"),
                    output_field=models.DecimalField(),
                )
                / total["outbound_requests"]
            )
        if total["queries_num"]:
            avg_aggregates.update(
                query_avg_time=models.Sum(
                    models.F("query_avg_time") * models.F("queries_num"),
                    output_field=models.DecimalField(),
                )
                / total["queries_num"]
            )
        if total["requests"]:
            avg_aggregates.update(
                avg_time=models.Sum(
                    models.F("avg_time") * models.F("requests"),
                    output_field=models.DecimalField(),
                )
                / total["requests"]
            )

        used_memory = self.get_total_memory()

        import psutil

        sys_total_memory = psutil.virtual_memory().total
        sys_cpu_num = os.cpu_count()

        total.update(
            used_memory=used_memory,
            memory_percent=round(100 * used_memory / sys_total_memory, 3),
        )

        return replace_null(
            dict(
                **self.connected_workers.aggregate(
                    total_net_connections=models.Sum("total_net_connections"),
                    active_net_connections=models.Sum("active_net_connections"),
                    file_descriptors=models.Sum("file_descriptors"),
                    cpu_percent=models.Sum("cpu_percent") / sys_cpu_num,
                    threads=models.Sum("threads"),
                    open_files=models.Sum("open_files"),
                    in_traffic=models.Sum("in_traffic"),
                    out_traffic=models.Sum("out_traffic"),
                    outbound_rps=models.Sum("outbound_rps"),
                    outbound_timeouts=models.Sum("outbound_timeouts"),
                    outbound_errors=models.Sum("outbound_errors"),
                    qps=models.Sum("qps"),
                    errors=models.Sum("errors"),
                    rps=models.Sum("rps"),
                    **avg_aggregates,
                ),
                **total,
            )
        )

    def monitor(self):
        if not self.config.monitor.server_disabled:
            try:
                self.server_monitor()
            except Exception as e:
                self.warn(f"utilmeta.ops.task: server monitor failed: {e}")
        if not self.config.monitor.instance_disabled:
            try:
                self.instance_monitor()
            except Exception as e:
                self.warn(f"utilmeta.ops.task: instance monitor failed: {e}")
        if not self.config.monitor.database_disabled:
            try:
                self.database_monitor()
            except Exception as e:
                self.warn(f"utilmeta.ops.task: database monitor failed: {e}")
        if not self.config.monitor.cache_disabled:
            try:
                self.cache_monitor()
            except Exception as e:
                self.warn(f"utilmeta.ops.task: cache monitor failed: {e}")

    def instance_monitor(self):
        if not self.instance:
            return
        workers_num = self.connected_workers.count()
        if not workers_num:
            # no workers
            return
        from .models import InstanceMonitor

        metrics = self.get_instance_metrics()
        # now = time_now()
        # last: InstanceMonitor = InstanceMonitor.objects.filter(
        #     instance=self,
        #     layer=0,
        # ).order_by('time').last()
        # data = dict(self.instance.data or {})
        # data.update(time=self._last_exec.timestamp())
        self.instance.updated_time = self._last_exec
        self.instance.save(update_fields=["updated_time"])
        InstanceMonitor.objects.create(
            time=self._last_exec,
            instance=self.instance,
            interval=self.interval,
            current_workers=workers_num,
            **metrics,
        )

    def server_monitor(self):
        from .models import ServerMonitor

        if not self.server:
            return
        metrics = get_sys_metrics(cpu_interval=self.DEFAULT_CPU_INTERVAL)
        try:
            l1, l5, l15 = psutil.getloadavg()
        except (AttributeError, OSError):
            l1, l5, l15 = 0, 0, 0
        loads = dict(load_avg_1=l1, load_avg_5=l5, load_avg_15=l15)
        ServerMonitor.objects.create(
            server=self.server,
            interval=self.interval,
            time=self._last_exec,
            **metrics,
            **loads,
        )

    def database_monitor(self):
        from .monitor import (
            get_db_size,
            get_db_transactions,
            get_db_connections,
            get_db_server_size,
            get_db_server_connections,
            get_db_connections_num,
            get_db_max_connections,
        )
        from utilmeta.core.orm import DatabaseConnections
        from .models import Resource, DatabaseMonitor, DatabaseConnection

        db_config = DatabaseConnections.config()
        if not db_config:
            return

        db_monitors = []
        update_databases = []
        update_conn = []
        create_conn = []
        for database in Resource.filter(
            type="database", node_id=self.node_id, ident__in=list(db_config.databases)
        ):
            database: Resource
            db = DatabaseConnections.get(database.ident)
            if not db:
                continue
            max_conn = get_db_max_connections(db.alias)
            transactions = get_db_transactions(db.alias)
            size = get_db_size(db.alias)
            connected = size is not None
            db_data = dict(database.data)
            current_transactions = db_data.get("transactions") or 0
            new_transactions = max(0, transactions - current_transactions)
            db_metrics = dict(
                max_server_connections=max_conn,
                used_space=size or 0,
                transactions=transactions,
                connected=connected,
            )
            db_data.update(db_metrics)
            database.updated_time = self._last_exec
            # update_fields = ['updated_time']
            if db_data != database.data:
                database.data = db_data
                # update_fields.append('data')
            # database.save(update_fields=update_fields)
            update_databases.append(database)
            current, active = get_db_connections_num(db.alias)
            db_monitors.append(
                DatabaseMonitor(
                    database=database,
                    interval=self.interval,
                    time=self._last_exec,
                    used_space=size or 0,
                    server_used_space=get_db_server_size(db.alias) or 0,
                    server_connections=get_db_server_connections(db.alias) or 0,
                    current_connections=current or 0,
                    active_connections=active or 0,
                    new_transactions=new_transactions,
                    metrics=db_metrics,
                )
            )
            connections = get_db_connections(db.alias)

            if connections:
                current_connections = list(
                    DatabaseConnection.objects.filter(database=database)
                )
                for conn in connections:
                    for c in current_connections:
                        c: DatabaseConnection
                        if c.pid == conn.pid:
                            conn.id = c.pk
                    conn.database_id = database.pk
                    if conn.id:
                        update_conn.append(conn)
                    else:
                        create_conn.append(conn)
        if db_monitors:
            DatabaseMonitor.objects.bulk_create(db_monitors)
        if update_databases:
            Resource.objects.bulk_update(
                update_databases, fields=["updated_time", "data"]
            )
        if create_conn:
            DatabaseConnection.objects.bulk_create(create_conn)
        if update_conn:
            DatabaseConnection.objects.bulk_update(
                update_conn,
                fields=[
                    "status",
                    "active",
                    "client_addr",
                    "client_port",
                    "pid",
                    "backend_start",
                    "query_start",
                    "state_change",
                    "wait_event",
                    "transaction_start",
                    "query",
                    "operation",
                    "tables",
                ],
            )
        if update_databases:
            DatabaseConnection.objects.filter(database__in=update_databases).exclude(
                pk__in=[conn.pk for conn in create_conn + update_conn]
            ).delete()

    def cache_monitor(self):
        from .monitor import get_cache_stats
        from .models import CacheMonitor, Resource
        from utilmeta.core.cache import CacheConnections

        cache_config = CacheConnections.config()
        if not cache_config:
            return
        updated_caches = []
        cache_monitors = []
        for cache_obj in Resource.filter(
            type="cache", node_id=self.node_id, ident__in=list(cache_config.caches)
        ):
            cache_obj: Resource
            cache = CacheConnections.get(cache_obj.ident)
            if not cache:
                continue

            stats = get_cache_stats(cache.alias)
            connected = stats is not None
            cache_data = dict(connected=connected)
            data = dict(stats or {})
            pid = data.get("pid")
            # cpu_percent = memory_percent = fds = open_files = None
            if pid and cache.local:
                try:
                    proc = psutil.Process(pid)
                    cpu_percent = proc.cpu_percent(0.5)
                    memory_percent = proc.memory_percent()
                    fds = proc.num_fds() if psutil.POSIX else None
                    open_files = len(proc.open_files())
                    data.update(
                        cpu_percent=cpu_percent,
                        memory_percent=memory_percent,
                        file_descriptors=fds,
                        open_files=open_files,
                    )
                except psutil.Error:
                    pass
                cache_data.update(pid=pid)

            cache.updated_time = self._last_exec
            # update_fields = ['updated_time']
            if cache_data != cache_obj.data:
                cache_obj.data = cache_data
                # update_fields.append('data')
            updated_caches.append(cache_obj)
            cache_monitors.append(
                CacheMonitor(
                    time=self._last_exec,
                    interval=self.interval,
                    cache=cache_obj,
                    **data,
                )
            )
        if updated_caches:
            Resource.objects.bulk_update(
                updated_caches, fields=["updated_time", "data"]
            )
        if cache_monitors:
            CacheMonitor.objects.bulk_create(cache_monitors)

    @ignore_errors
    def clear(self):
        from .models import (
            ServiceLog,
            RequestLog,
            QueryLog,
            VersionLog,
            WorkerMonitor,
            CacheMonitor,
            InstanceMonitor,
            ServerMonitor,
            DatabaseMonitor,
            AggregationLog,
            AlertLog,
            Worker,
            Resource,
        )

        now = self._last_exec or time_now()
        ServiceLog.objects.filter(
            time__lt=now - self.config.log.volatile_maintain, volatile=True
        ).delete()

        # MAX RETENTION ------------------
        max_retention_time = timedelta(seconds=self.config.max_retention_time)
        ServiceLog.objects.filter(
            time__lt=now - max_retention_time,
        ).delete()
        RequestLog.objects.filter(
            time__lt=now - max_retention_time,
        ).delete()
        QueryLog.objects.filter(
            time__lt=now - max_retention_time,
        ).delete()
        VersionLog.objects.filter(
            time__lt=now - max_retention_time,
        ).delete()
        AlertLog.objects.filter(
            time__lt=now - max_retention_time,
        ).delete()
        AggregationLog.objects.filter(
            to_time__lt=now - max_retention_time,
        ).delete()
        # ---------------------------------
        # WORKER RETENTION ----------------
        WorkerMonitor.objects.filter(
            time__lt=now - self.config.monitor.worker_retention
        ).delete()
        Worker.objects.filter(
            time__lt=now - self.DISCONNECTED_WORKER_RETENTION, connected=False
        ).delete()

        # MONITOR RETENTION ----------------
        Resource.objects.filter(type="instance", node_id=self.node_id,).annotate(
            latest_time=models.Max("instance_metrics__time")
        ).filter(latest_time__lt=now - self.DISCONNECTED_INSTANCE_RETENTION).update(
            deleted_time=now, deprecated=True
        )
        InstanceMonitor.objects.filter(
            layer=0, time__lt=now - self.config.monitor.instance_retention
        ).delete()

        Resource.objects.filter(type="server", node_id=self.node_id,).annotate(
            latest_time=models.Max("server_metrics__time")
        ).filter(latest_time__lt=now - self.DISCONNECTED_SERVER_RETENTION).update(
            deleted_time=now, deprecated=True
        )
        ServerMonitor.objects.filter(
            layer=0, time__lt=now - self.config.monitor.server_retention
        ).delete()

        DatabaseMonitor.objects.filter(
            layer=0, time__lt=now - self.config.monitor.database_retention
        ).delete()
        CacheMonitor.objects.filter(
            layer=0, time__lt=now - self.config.monitor.cache_retention
        ).delete()

    def alert(self):
        pass

    @property
    def is_worker_primary(self):
        # if not self.worker:
        #     return False
        if not self.instance or not self.server or not self.worker:
            return False
        return not self.connected_workers.filter(
            # pid__lt=os.getpid()
            start_time__lt=self.worker.start_time
        ).exists()

    @property
    def current_day(self) -> datetime:
        t = self._last_exec or time_now()
        return datetime(year=t.year, month=t.month, day=t.day, tzinfo=t.tzinfo)

    @property
    def current_hour(self) -> datetime:
        t = self._last_exec or time_now()
        return datetime(
            year=t.year, month=t.month, day=t.day, hour=t.hour, tzinfo=t.tzinfo
        )

    @property
    def utc_day_begin(self):
        return self._last_exec.astimezone(timezone.utc).hour == 0

    @property
    def daily_report(self):
        if self.daily_aggregation:
            if self.daily_aggregation.to_time == self.current_day:
                # already
                return False
        if not self.is_worker_primary:
            # check here also
            return False
        if not self.hourly_aggregation:
            # wait for at least an hourly aggregation
            return False
        return True

    @ignore_errors
    def aggregation(self):
        self.logs_aggregation(0)

        if self.daily_report:
            # 1. it is the UTC begin
            # 2. daily aggregation not generated
            # 3. hourly aggregation already generated and reported
            self.logs_aggregation(1)

    def logs_aggregation(self, layer: int = 0):
        #  HOURLY
        if layer == 0:
            current_time = self.current_hour
            aggregation = self.hourly_aggregation
        elif layer == 1:
            current_time = self.current_day
            aggregation = self.daily_aggregation
        else:
            return

        interval = [timedelta(hours=1), timedelta(days=1)][layer]
        last_time = current_time - interval
        from .models import AggregationLog

        if not aggregation or aggregation.from_time != current_time:
            aggregation: AggregationLog = AggregationLog.objects.filter(
                service=self.service.name,
                node_id=self.node_id,
                supervisor=self.supervisor,
                from_time=last_time,
                to_time=current_time,
                layer=layer,
            ).first()

        if not aggregation:
            service_data = aggregate_logs(
                service=self.service.name, to_time=current_time, layer=layer
            )
            endpoints = (
                aggregate_endpoint_logs(
                    service=self.service.name, to_time=current_time, layer=layer
                )
                if service_data
                else None
            )
            aggregation = AggregationLog.objects.create(
                service=self.service.name,
                node_id=self.node_id,
                supervisor=self.supervisor,
                data=normalize(
                    dict(
                        service=service_data,
                        endpoints=endpoints,
                    ),
                    _json=True,
                ),
                layer=layer,
                from_time=last_time,
                to_time=current_time,
                reported_time=self._last_exec if not service_data else None,
            )

            # check daily ---------------------------------------------
        else:
            service_data = (aggregation.data or {}).get("service")

        if layer == 0:
            self.hourly_aggregation = aggregation
        elif layer == 1:
            self.daily_aggregation = aggregation

        if aggregation.reported_time:
            return

        # daily ?

        if not service_data:
            return
        if self.config.report_disabled:
            return
        if not self.node_id:
            return

        report = False
        layer_seconds = int(self.LAYER_INTERVAL[layer].total_seconds())

        if layer == 1:
            if self.hourly_aggregation:
                if self.hourly_aggregation.to_time == current_time:
                    if self.hourly_aggregation.reported_time:
                        report = True
                elif self.hourly_aggregation.to_time > current_time:
                    # already ahead of this layer 1 aggregation
                    report = True
        else:
            prob_1 = (
                (self._last_exec - current_time).total_seconds() + self.interval * 2
            ) / layer_seconds
            prob = (2 * self.interval / layer_seconds) + prob_1
            if prob_1 >= 1:
                report = True
            else:
                report = random.random() < prob

        if not report:
            return
        if not self.supervisor:
            return
        if self.supervisor.local:
            return

        from .client import SupervisorClient, SupervisorReportResponse

        with SupervisorClient(
            node_id=self.node_id,
            default_timeout=self.config.default_timeout,
            fail_silently=True,
        ) as client:
            resp = client.report_analytics(
                data=dict(
                    time=current_time.astimezone(timezone.utc),
                    layer=layer,
                    interval=layer_seconds,
                    **aggregation.data,
                )
            )
            updates = {}
            if not resp.success:
                updates.update(error=resp.message)
            else:
                aggregation.reported_time = resp.time or self._last_exec
                updates.update(
                    remote_id=resp.result.id, reported_time=aggregation.reported_time
                )

            AggregationLog.objects.filter(pk=aggregation.pk).update(**updates)

            success = isinstance(resp, SupervisorReportResponse) and resp.success
            if not success:
                return

            # if this report is successful, we can check if there are missing reports
            missing_reports = (
                AggregationLog.objects.filter(
                    supervisor=self.supervisor,
                    # layer=layer,
                    # no restrict on the layer
                    reported_time=None,
                    created_time__gte=self._last_exec
                    - self.AGGREGATION_EXPIRE_TIME[layer],
                )
                .order_by("to_time")
                .exclude(pk=aggregation.pk)
            )

            missing_count = missing_reports.count()
            if missing_count:
                batch_size = self.REPORT_BATCH_MAX_SIZE
                empty_missing_reports = []
                updates = []
                errors = []

                for offset in range(0, missing_count, batch_size):
                    batch_missing_reports = []
                    # using batch to handle history missing report
                    # avoid sending massive reports
                    values = []
                    for obj in list(missing_reports[offset: offset + batch_size]):
                        obj: AggregationLog
                        service = obj.data.get("service")
                        if not service:
                            empty_missing_reports.append(obj)
                            continue
                        batch_missing_reports.append(obj)
                        values.append(
                            dict(
                                time=obj.to_time.astimezone(timezone.utc),
                                layer=obj.layer,
                                interval=layer_seconds,
                                **obj.data,
                            )
                        )
                    if values:
                        resp = client.batch_report_analytics(data=values)
                        if isinstance(resp.result, list):

                            for res, report in zip(resp.result, batch_missing_reports):
                                remote_id = (
                                    res.get("id") if isinstance(res, dict) else None
                                )
                                if remote_id:
                                    updates.append(
                                        AggregationLog(
                                            id=report.pk,
                                            remote_id=remote_id,
                                            reported_time=resp.time or self._last_exec,
                                        )
                                    )
                                else:
                                    errors.append(
                                        AggregationLog(
                                            id=report.pk,
                                            error=res.get("error", str(res))
                                            if isinstance(res, dict)
                                            else str(res),
                                        )
                                    )

                if updates:
                    AggregationLog.objects.bulk_update(
                        updates,
                        fields=["remote_id", "reported_time"],
                        batch_size=self.UPDATE_BATCH_MAX_SIZE,
                    )
                if errors:
                    AggregationLog.objects.bulk_update(
                        errors, fields=["error"], batch_size=self.UPDATE_BATCH_MAX_SIZE
                    )
                if empty_missing_reports:
                    AggregationLog.objects.filter(
                        pk__in=[obj.pk for obj in empty_missing_reports]
                    ).update(reported_time=self._last_exec or time_now())

    def heartbeat(self):
        pass
