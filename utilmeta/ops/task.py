import os
from .config import Operations
from .log import setup_locals, batch_save_logs, worker_logger
from .monitor import get_sys_metrics
import psutil
from utilmeta.utils import time_now, replace_null, Error, normalize
from datetime import timedelta, datetime, timezone
from django.db import models
from django.db.utils import OperationalError, ProgrammingError
from .aggregation import aggregate_logs, aggregate_endpoint_logs
from typing import Optional
import random
import time


class BaseCycleTask:
    def __init__(self, interval: int):
        self.interval = interval
        self._stopped = False
        self._last_exec: Optional[datetime] = None

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
            try:
                if not self():
                    break
            except Exception as e:
                err = Error(e)
                err.setup()
                print(err.full_info)
            if self._stopped:
                break
            wait_for = max(0.0, self.interval - (time_now() - self._last_exec).total_seconds())
            if wait_for:
                time.sleep(wait_for)

    def exit_gracefully(self, signum, frame):
        self.stop(wait=False)

    def stop(self, wait: bool = False):
        self._stopped = True


class OperationWorkerTask(BaseCycleTask):
    WORKER_MONITOR_RETENTION = timedelta(hours=12)
    DISCONNECTED_WORKER_RETENTION = timedelta(hours=12)
    DISCONNECTED_INSTANCE_RETENTION = timedelta(days=3)
    DISCONNECTED_SERVER_RETENTION = timedelta(days=3)
    SERVER_MONITOR_RETENTION = timedelta(days=7)
    INSTANCE_MONITOR_RETENTION = timedelta(days=7)
    VOLATILE_LOGS_RETENTION = timedelta(days=7)
    AGGREGATION_EXPIRE_TIME = [timedelta(days=1), timedelta(days=7)]

    LAYER_INTERVAL = [timedelta(hours=1), timedelta(days=1)]
    DEFAULT_CPU_INTERVAL = 1

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

    def __call__(self, *args, **kwargs):
        self.worker_cycle()
        return True

    @property
    def node_id(self):
        return self.supervisor.node_id if self.supervisor else None

    def migrate_ops(self):
        from django.db.migrations.executor import MigrationExecutor
        from django.db import connections, connection
        ops_conn = connections[self.config.db_alias]
        executor = MigrationExecutor(ops_conn)
        migrate_apps = ['ops', 'contenttypes']
        targets = [
            key for key in executor.loader.graph.leaf_nodes() if key[0] in migrate_apps
        ]
        plan = executor.migration_plan(targets)
        if not plan:
            return
        executor.migrate(targets, plan)
        # ----------
        if connection != ops_conn:
            executor = MigrationExecutor(connection)
            targets = [
                key for key in executor.loader.graph.leaf_nodes() if key[0] in migrate_apps
            ]
            plan = executor.migration_plan(targets)
            if not plan:
                return
            executor.migrate(targets, plan)

    def worker_cycle(self):
        if not self._last_exec:
            self._last_exec = time_now()

        if not self._init_cycle:
            self.migrate_ops()
            # 1. db not created
            # 2. db not updated to the current version

        setup_locals(self.config)

        # try to set up locals before
        from .log import _server, _worker, _instance, _supervisor
        self.worker = _worker
        self.server = _server
        self.instance = _instance
        self.supervisor = _supervisor

        # 1. save logs
        batch_save_logs()

        # 2. update worker
        worker_logger.update_worker(
            record=True,
            interval=self.config.worker_cycle
        )

        # update worker from every worker
        # to make sure that the connected workers has the primary role to execute the following
        self.update_workers()

        if self._stopped:
            # if this worker is stopped
            # we exit right after collect all the memory-stored logs
            # other process (aka. the restarted process) will be take care of the rest
            return

        if self.is_worker_primary:
            # Is this worker the primary worker of the current instance
            # detect the running worker with the minimum PID
            self.server_monitor()
            self.instance_monitor()
            self.heartbeat()
            self.alert()
            self.aggregation()
            self.clear()

            if not self._init_cycle:
                # 1st cycle
                resources = self.config.resources_manager_cls(self.service)
                resources.sync_resources(self.supervisor)
                # try to update

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

        Worker.objects.filter(
            instance=self.instance
        ).filter(
            models.Q(
                time__lte=time_now() - timedelta(
                    seconds=self.interval * 2
                )
            ) | models.Q(
                pk__in=disconnected
            )
        ).update(connected=False)

    def get_total_memory(self):
        mem = 0
        try:
            for pss, uss in self.connected_workers.values_list('memory_info__pss', 'memory_info__uss'):
                mem += pss or uss or 0
        except Exception:   # noqa
            # field error / Operational error
            # maybe sqlite, not support json lookup
            for mem_info in self.connected_workers.values_list('memory_info', flat=True):
                mem += mem_info.get('pss') or mem_info.get('uss') or 0
        return mem

    def get_instance_metrics(self):
        total = self.connected_workers.aggregate(
            outbound_requests=models.Sum('outbound_requests'),
            queries_num=models.Sum('queries_num'),
            requests=models.Sum('requests')
        )
        avg_aggregates = {}
        if total['outbound_requests']:
            avg_aggregates.update(
                outbound_avg_time=models.Sum(models.F('outbound_avg_time') * models.F('outbound_requests'),
                                             output_field=models.DecimalField()) / total['outbound_requests'])
        if total['queries_num']:
            avg_aggregates.update(
                query_avg_time=models.Sum(models.F('query_avg_time') *
                                       models.F('queries_num'),
                                          output_field=models.DecimalField()) / total['queries_num'])
        if total['requests']:
            avg_aggregates.update(avg_time=models.Sum(models.F('avg_time') * models.F('requests'),
                                                      output_field=models.DecimalField()) / total['requests'])

        used_memory = self.get_total_memory()

        import psutil
        sys_total_memory = psutil.virtual_memory().total
        sys_cpu_num = os.cpu_count()

        total.update(
            used_memory=used_memory,
            memory_percent=round(100 * used_memory / sys_total_memory, 3)
        )

        return replace_null(dict(**self.connected_workers.aggregate(
            total_net_connections=models.Sum('total_net_connections'),
            active_net_connections=models.Sum('active_net_connections'),
            file_descriptors=models.Sum('file_descriptors'),
            cpu_percent=models.Sum('cpu_percent') / sys_cpu_num,
            threads=models.Sum('threads'),
            open_files=models.Sum('open_files'),
            in_traffic=models.Sum('in_traffic'),
            out_traffic=models.Sum('out_traffic'),
            outbound_rps=models.Sum('outbound_rps'),
            outbound_timeouts=models.Sum('outbound_timeouts'),
            outbound_errors=models.Sum('outbound_errors'),
            qps=models.Sum('qps'),
            errors=models.Sum('errors'),
            rps=models.Sum('rps'),
            **avg_aggregates,
        ), **total))

    def instance_monitor(self):
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
        InstanceMonitor.objects.create(
            time=self._last_exec,
            instance=self.instance,
            interval=self.interval,
            current_workers=workers_num,
            **metrics
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
        loads = dict(
            load_avg_1=l1,
            load_avg_5=l5,
            load_avg_15=l15
        )
        ServerMonitor.objects.create(
            server=self.server,
            interval=self.interval,
            time=self._last_exec,
            **metrics,
            **loads
        )

    def clear(self):
        from .models import ServiceLog, RequestLog, QueryLog, VersionLog, WorkerMonitor, CacheMonitor, \
            InstanceMonitor, ServerMonitor, DatabaseMonitor, AggregationLog, AlertLog, Worker, Resource
        now = self._last_exec or time_now()
        ServiceLog.objects.filter(
            time__lt=now - self.VOLATILE_LOGS_RETENTION,
            volatile=True
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
        )
        AlertLog.objects.filter(
            time__lt=now - max_retention_time,
        )
        AggregationLog.objects.filter(
            to_time__lt=now - max_retention_time,
        )
        # ---------------------------------
        # WORKER RETENTION ----------------
        WorkerMonitor.objects.filter(
            time__lt=now - self.WORKER_MONITOR_RETENTION
        ).delete()
        Worker.objects.filter(
            time__lt=now - self.DISCONNECTED_WORKER_RETENTION,
            connected=False
        ).delete()

        # MONITOR RETENTION ----------------
        Resource.objects.filter(
            type='instance',
            node_id=self.node_id,
        ).annotate(
            latest_time=models.Max('instance_metrics__time')
        ).filter(
            latest_time__lt=now - self.DISCONNECTED_INSTANCE_RETENTION
        ).update(deleted_time=now, deprecated=True)
        InstanceMonitor.objects.filter(
            layer=0,
            time__lt=now - self.INSTANCE_MONITOR_RETENTION
        ).delete()

        Resource.objects.filter(
            type='server',
            node_id=self.node_id,
        ).annotate(
            latest_time=models.Max('server_metrics__time')
        ).filter(
            latest_time__lt=now - self.DISCONNECTED_SERVER_RETENTION
        ).update(deleted_time=now, deprecated=True)
        ServerMonitor.objects.filter(
            layer=0,
            time__lt=now - self.SERVER_MONITOR_RETENTION
        ).delete()

        DatabaseMonitor.objects.filter(
            layer=0,
            time__lt=now - self.SERVER_MONITOR_RETENTION
        ).delete()
        CacheMonitor.objects.filter(
            layer=0,
            time__lt=now - self.SERVER_MONITOR_RETENTION
        ).delete()

    def alert(self):
        pass

    @property
    def is_worker_primary(self):
        # if not self.worker:
        #     return False
        if not self.instance:
            return False
        from .models import Worker
        return not Worker.objects.filter(
            instance=self.instance,
            connected=True,
            pid__lt=os.getpid()
        ).exists()

    @property
    def current_day(self) -> datetime:
        t = self._last_exec or time_now()
        return datetime(
            year=t.year,
            month=t.month,
            day=t.day,
            tzinfo=t.tzinfo
        )

    @property
    def current_hour(self) -> datetime:
        t = self._last_exec or time_now()
        return datetime(
            year=t.year,
            month=t.month,
            day=t.day,
            hour=t.hour,
            tzinfo=t.tzinfo
        )

    @property
    def utc_day_begin(self):
        return self._last_exec.astimezone(timezone.utc).hour == 0

    def aggregation(self):
        self.logs_aggregation(0)

        if self.utc_day_begin or not self.daily_aggregation or \
                (not self.daily_aggregation.reported_time and
                 self.hourly_aggregation and self.hourly_aggregation.reported_time):
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
                layer=layer
            ).first()

        if not aggregation:
            service_data = aggregate_logs(
                service=self.service.name,
                to_time=current_time,
                layer=layer
            )
            endpoints = aggregate_endpoint_logs(
                service=self.service.name,
                to_time=current_time,
                layer=layer
            ) if service_data else None
            aggregation = AggregationLog.objects.create(
                service=self.service.name,
                node_id=self.node_id,
                supervisor=self.supervisor,
                data=normalize(dict(
                    service=service_data,
                    endpoints=endpoints,
                ), _json=True),
                layer=layer,
                from_time=last_time,
                to_time=current_time,
                reported_time=self._last_exec if not service_data else None
            )

            # check daily ---------------------------------------------
        else:
            service_data = (aggregation.data or {}).get('service')

        if layer == 0:
            self.hourly_aggregation = aggregation
        elif layer == 1:
            self.daily_aggregation = aggregation

        if aggregation.reported_time:
            return

        # daily ?

        if not service_data:
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
                    report = True
        else:
            prob_1 = ((self._last_exec - current_time).total_seconds() + self.interval * 2) / layer_seconds
            prob = (2 * self.interval / layer_seconds) + prob_1
            if prob_1 >= 1:
                report = True
            else:
                report = random.random() < prob

        if not report:
            return

        from .client import SupervisorClient

        with SupervisorClient(
            node_id=self.node_id,
            default_timeout=self.config.default_timeout
        ) as client:
            resp = client.report_analytics(
                data=dict(
                    time=current_time.astimezone(timezone.utc),
                    layer=layer,
                    interval=layer_seconds,
                    **aggregation.data
                )
            )
            updates = {}
            if not resp.success:
                updates.update(error=resp.message)
            else:
                updates.update(
                    remote_id=resp.result.id,
                    reported_time=resp.time or self._last_exec
                )

            AggregationLog.objects.filter(
                pk=aggregation.pk
            ).update(**updates)

            # if this report is successful, we can check if there are missing reports
            for obj in AggregationLog.objects.filter(
                supervisor=self.supervisor,
                layer=layer,
                reported_time=None,
                created_time__gte=self._last_exec - self.AGGREGATION_EXPIRE_TIME[layer]
            ).order_by('to_time').exclude(pk=aggregation.pk):
                obj: AggregationLog
                service = obj.data.get('service')
                if not service:
                    continue
                resp = client.report_analytics(
                    data=dict(
                        time=obj.to_time.astimezone(timezone.utc),
                        layer=obj.layer,
                        interval=layer_seconds,
                        **obj.data
                    )
                )
                updates = {}
                if not resp.success:
                    updates.update(error=resp.message)
                else:
                    updates.update(
                        remote_id=resp.result.id,
                        reported_time=resp.time or self._last_exec
                    )
                AggregationLog.objects.filter(
                    pk=obj.pk
                ).update(**updates)

    def heartbeat(self):
        pass
