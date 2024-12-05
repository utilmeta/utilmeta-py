from django.db import models
from utype.types import *
from utilmeta.utils import time_now, convert_time
from utype import JSONEncoder


class Supervisor(models.Model):
    objects = models.Manager()

    service = models.CharField(max_length=100)
    node_id = models.CharField(max_length=40, default=None, null=True)

    ident = models.CharField(max_length=20, default=None, null=True)
    # offline_enabled = BooleanField(default=True)
    # enable offline (ak/signature-only, no remote-auth/token-retrieve) to open resources to utilmeta ecosystem
    backup_urls = models.JSONField(default=list, encoder=JSONEncoder)
    # direct callback to master url, like https://utilmeta.com/api/action/backup?id=<ID> for backup node servers
    base_url = models.URLField()
    # remote_ops_api = URLField(default=None, null=True)
    # when local ops_api changed on proxy (including base_url/host altered)
    # action_token = models.CharField(max_length=64, unique=True)
    # platform can carry this token to identify itself
    local = models.BooleanField(default=False)
    # REMOTE FOR LOCAL NODE

    # <not> public actually
    public_key = models.TextField(default=None, null=True)  # used to decode token
    # None when generated as placeholder

    init_key = models.TextField(default=None, null=True)
    # used to identify the init add supervisor request

    created_time = models.DateTimeField(auto_now_add=True)

    ops_api = models.URLField()  # correlate with node.ops_api in platform
    # if ops_api is different from the new version ops api
    # will require an update
    url = models.URLField(default=None, null=True)

    operation_timeout = models.DecimalField(max_digits=8, decimal_places=3, default=None, null=True)
    # open_scopes = models.JSONField(default=list)
    # disabled_scopes = models.JSONField(default=list)

    heartbeat_interval = models.PositiveIntegerField(default=None, null=True)
    # open for every request user
    latency = models.PositiveIntegerField(default=None, null=True)  # ms

    settings: dict = models.JSONField(default=dict, encoder=JSONEncoder)
    # heartbeat_enabled: False
    # report_enabled: true
    # notify_enabled: false
    # users_analytics: false
    # endpoints_analytics: false

    # info = models.JSONField(default=dict)  # store backward compat information
    connected = models.BooleanField(default=False)
    disabled = models.BooleanField(default=False)

    # -- advanced
    alert_settings: dict = models.JSONField(default=dict, encoder=JSONEncoder)
    task_settings: dict = models.JSONField(default=dict, encoder=JSONEncoder)
    # heartbeat_settings: dict = models.JSONField(default=dict)
    aggregate_settings: dict = models.JSONField(default=dict, encoder=JSONEncoder)

    data = models.JSONField(default=dict, encoder=JSONEncoder)

    resources_etag = models.TextField(default=None, null=True)
    # if resources etag doesn't change
    # there is not need to re-update
    # etag is generated from supervisor

    class Meta:
        db_table = 'utilmeta_supervisor'

    @classmethod
    def filter(cls, *args, **kwargs) -> models.QuerySet:
        q = models.Q(
            local=True
        ) | models.Q(
            public_key__isnull=False,
        )
        kwargs.update(
            node_id__isnull=False,
            disabled=False
        )
        return cls.objects.filter(*args, q, **kwargs)

    @classmethod
    def current(cls) -> models.QuerySet:
        from .config import Operations
        config = Operations.config()
        kwargs = {}
        if config and config.node_id:
            kwargs.update(node_id=config.node_id)
        else:
            from utilmeta import service
            kwargs.update(service=service.name)
        return cls.filter(**kwargs)


class AccessToken(models.Model):
    objects = models.Manager()

    issuer = models.ForeignKey(Supervisor, related_name='access_tokens', on_delete=models.CASCADE)
    token_id = models.CharField(max_length=200, unique=True)
    issued_at = models.DateTimeField(default=None, null=True)
    subject = models.CharField(max_length=500, default=None, null=True)
    expiry_time = models.DateTimeField(default=None, null=True)
    # clear tokens beyond the expiry time

    # ACTIVITY -----------------
    last_activity = models.DateTimeField(default=None, null=True)
    used_times = models.PositiveIntegerField(default=0)
    ip = models.GenericIPAddressField(default=None, null=True)

    # PERMISSION ---------------
    scope = models.JSONField(default=list, encoder=JSONEncoder)
    # excludes = models.JSONField(default=list)
    # readonly = models.BooleanField(default=False)
    # -------

    revoked = models.BooleanField(default=False)
    # revoke tokens of a subject if it's permission is changed or revoked

    class Meta:
        db_table = 'utilmeta_access_token'


class Resource(models.Model):
    objects = models.Manager()

    # id = models.CharField(max_length=40, primary_key=True)
    service = models.CharField(max_length=100, null=True)
    node_id = models.CharField(max_length=100, default=None, null=True, db_index=True)
    # common utils like server, service is None
    type = models.CharField(max_length=40)
    # server
    # instance
    # task
    # endpoint
    # table (data model)
    # database
    # cache
    ident = models.CharField(max_length=200)
    route = models.CharField(max_length=500)
    # :type/:node/:ident
    ref = models.CharField(max_length=500, default=None, null=True)

    remote_id = models.CharField(max_length=100, default=None, null=True)
    # id_map = models.JSONField(default=dict)
    # supervisor: id
    # remote_id = models.CharField(max_length=40, default=None, null=True)
    # supervisor = models.ForeignKey(Supervisor, related_name='resources', on_delete=models.CASCADE)

    server = models.ForeignKey(
        'self', related_name='resources',
        on_delete=models.SET_NULL,
        default=None, null=True
    )
    server_id: Optional[int]
    data: dict = models.JSONField(default=dict, encoder=JSONEncoder)

    created_time = models.DateTimeField(auto_now_add=True)
    updated_time = models.DateTimeField(default=None, null=True)
    deleted_time = models.DateTimeField(default=None, null=True)

    deprecated = models.BooleanField(default=False)
    # endpoint / table -> deprecated
    # server / instance / database / cached -> disconnected

    class Meta:
        db_table = 'utilmeta_resource'

    @classmethod
    def filter(cls, *args, **kwargs):
        kwargs.update(deleted_time=None)
        return cls.objects.filter(*args, **kwargs)

    @classmethod
    def get_current_server(cls) -> Optional['Resource']:
        # from utilmeta.utils import get_server_ip
        from utilmeta.utils import get_mac_address
        return cls.filter(
            type='server',
            ident=get_mac_address(),
        ).order_by('-remote_id', 'deprecated', '-created_time').first()
        # first go with the remote_id

    @classmethod
    def get_current_instance(cls) -> Optional['Resource']:
        from utilmeta import service
        from .config import Operations
        config = service.get_config(Operations)
        return cls.filter(
            type='instance',
            service=service.name,
            ident=config.address
            # server=cls.get_current_server(),
        ).first()


class SystemMetrics(models.Model):
    objects = models.Manager()

    cpu_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    memory_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    used_memory = models.PositiveBigIntegerField(default=0)
    disk_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    file_descriptors = models.PositiveIntegerField(default=None, null=True)
    open_files = models.PositiveBigIntegerField(default=None, null=True)
    active_net_connections = models.PositiveIntegerField(default=0)
    total_net_connections = models.PositiveIntegerField(default=0)
    net_connections_info = models.JSONField(default=dict, encoder=JSONEncoder)

    class Meta:
        abstract = True


class DatabaseConnection(models.Model):
    objects = models.Manager()

    database: Resource = models.ForeignKey(Resource, related_name='database_connections', on_delete=models.CASCADE)
    # remote_id = CharField(max_length=100)
    status = models.CharField(max_length=40)
    active = models.BooleanField(default=False)
    client_addr = models.GenericIPAddressField()   # mysql use ADDR:PORT as HOST
    client_port = models.PositiveIntegerField()
    pid = models.PositiveIntegerField(default=None, null=True)

    query = models.TextField(default='')
    operation = models.CharField(max_length=32, default=None, null=True)
    tables = models.JSONField(default=list, encoder=JSONEncoder)

    backend_start = models.DateTimeField(default=None, null=True)
    transaction_start = models.DateTimeField(default=None, null=True)
    wait_event = models.TextField(default=None, null=True)
    query_start = models.DateTimeField(default=None, null=True)
    state_change = models.DateTimeField(default=None, null=True)

    data = models.JSONField(default=dict, encoder=JSONEncoder)

    class Meta:
        db_table = 'utilmeta_database_connection'
        # unique_together = ('database', 'remote_id')


class ServiceMetrics(models.Model):
    """
    request metrics that can simply be calculated in form of incr and divide
    """
    in_traffic = models.PositiveBigIntegerField(default=0, null=True)    # in bytes
    out_traffic = models.PositiveBigIntegerField(default=0, null=True)    # in bytes
    # avg process time of requests made from this service
    outbound_requests = models.PositiveIntegerField(default=0)      # total request log count
    outbound_rps = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    outbound_timeouts = models.PositiveBigIntegerField(default=0)    # total timeout outbound_requests
    outbound_errors = models.PositiveBigIntegerField(default=0)      # total error outbound_requests
    outbound_avg_time = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    queries_num = models.PositiveBigIntegerField(default=0)
    query_avg_time = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    qps = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # requests
    requests = models.PositiveBigIntegerField(default=0)
    # requests made from current service to target instance
    rps = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    errors = models.PositiveBigIntegerField(default=0)
    # error requests made from current service to target instance
    avg_time = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    # avg process time of requests made from this service

    class Meta:
        abstract = True


class Worker(SystemMetrics, ServiceMetrics):
    server = models.ForeignKey(Resource, related_name='server_workers', on_delete=models.CASCADE)
    instance = models.ForeignKey(Resource, related_name='instance_workers', on_delete=models.CASCADE)

    pid: int = models.PositiveIntegerField()
    memory_info = models.JSONField(default=dict, encoder=JSONEncoder)
    threads = models.PositiveIntegerField(default=0)
    start_time: datetime = models.DateTimeField(default=time_now)
    # utility = ForeignKey(ServiceUtility, related_name='workers', on_delete=SET_NULL, null=True, default=None)
    master = models.ForeignKey('self', related_name='workers', on_delete=models.CASCADE, null=True, default=None)
    connected = models.BooleanField(default=True)
    # type = ChoiceField(WorkerType.gen(), retrieve_key=False, store_key=False, default=WorkerType.common)
    time: datetime = models.DateTimeField(default=time_now)  # latest metrics update time

    status = models.CharField(max_length=100, default=None, null=True)
    user = models.CharField(max_length=100, default=None, null=True)

    retire_time = models.DateTimeField(default=None, null=True)    # only work for task worker for now
    reload_params = models.JSONField(default=dict, encoder=JSONEncoder)
    # worker reload_on_rss (for uwsgi)
    # task.max_worker_memory (for task)
    # info = models.JSONField(default=dict)      # store backward compat information
    data = models.JSONField(default=dict, encoder=JSONEncoder)

    class Meta:
        db_table = 'utilmeta_worker'
        unique_together = ('server', 'pid')

    @classmethod
    def get(cls, pid: int):
        if not pid:
            return None
        return cls.objects.filter(pid=pid, server=Resource.get_current_server()).first()

    def get_sys_metrics(self):
        import psutil
        try:
            process = psutil.Process(self.pid)
        except psutil.Error:
            return None
        mem_info = process.memory_full_info()

        try:
            open_files = len(process.open_files())
        except psutil.Error:
            open_files = 0
        try:
            net_connections = getattr(process, 'net_connections', getattr(process, 'connections'))()
        except (psutil.Error, AttributeError):
            net_connections = []
        return dict(
            used_memory=getattr(mem_info, 'uss', getattr(mem_info, 'rss', 0)) or 0,
            memory_info={f: getattr(mem_info, f) for f in getattr(mem_info, '_fields')},
            total_net_connections=len(net_connections),
            active_net_connections=len([c for c in net_connections if c.status != 'CLOSE_WAIT']),
            file_descriptors=process.num_fds() if psutil.POSIX else None,
            cpu_percent=process.cpu_percent(interval=1),
            memory_percent=round(process.memory_percent('uss'), 2),
            open_files=open_files,
            threads=process.num_threads(),
        )

    @classmethod
    def load(cls, pid: int = None, **kwargs) -> Optional['Worker']:
        import psutil
        import os
        pid = pid or os.getpid()
        try:
            proc = psutil.Process(pid)
        except psutil.Error:
            return None
        server = Resource.get_current_server()
        if not server:
            return None
        instance = Resource.get_current_instance()
        if not instance:
            return None

        parent_pid = None
        if proc.parent():
            parent_pid = proc.parent().pid

        data = dict(
            start_time=convert_time(datetime.fromtimestamp(proc.create_time())),
            user=proc.username(),
            status=proc.status(),
        )

        data.update(kwargs)
        master = cls.objects.filter(
            pid=parent_pid,
            server=server,
            instance=instance
        ).first()

        if master:
            data.update(master_id=master.pk)    # do not user master=

        # prevent transaction
        worker_qs = cls.objects.filter(
            server_id=server.pk,
            pid=pid,
        )
        if worker_qs.exists():
            # IMPORTANT: update time as soon as Worker.load is triggered
            # to provide realtime metrics for representative
            data.update(
                time=time_now(),
                connected=True
            )
            worker_qs.update(**data)
            return worker_qs.first()

        from django.db.utils import IntegrityError
        try:
            return cls.objects.create(
                server=server,
                instance=instance,
                pid=pid,
                **data
            )
        except IntegrityError:
            return worker_qs.first()


class ServerMonitor(SystemMetrics):
    time = models.DateTimeField(default=time_now)
    # task_settings = ForeignKey(TaskSettings, on_delete=SET_NULL, default=None, null=True)
    layer = models.PositiveSmallIntegerField(default=0)
    interval = models.PositiveIntegerField(default=None, null=True)  # in seconds
    server = models.ForeignKey(Resource, related_name='server_metrics', on_delete=models.CASCADE)
    # version = ForeignKey(VersionLog, on_delete=SET_NULL, null=True, default=None)
    load_avg_1 = models.DecimalField(max_digits=8, decimal_places=2, default=None, null=True)
    load_avg_5 = models.DecimalField(max_digits=8, decimal_places=2, default=None, null=True)
    load_avg_15 = models.DecimalField(max_digits=8, decimal_places=2, default=None, null=True)
    # alert = ForeignKey(AlertLog, related_name='source_metrics', on_delete=SET_NULL, null=True, default=None)
    metrics = models.JSONField(default=dict, encoder=JSONEncoder)

    class Meta:
        db_table = 'utilmeta_server_monitor'
        ordering = ('time',)

    @classmethod
    def current(cls) -> Optional['ServerMonitor']:
        return cls.objects.last()   # already order by time


class WorkerMonitor(SystemMetrics, ServiceMetrics):
    time = models.DateTimeField(default=time_now)
    interval = models.PositiveIntegerField(default=None, null=True)  # in seconds
    worker = models.ForeignKey(Worker, related_name='worker_metrics', on_delete=models.CASCADE)
    memory_info = models.JSONField(default=dict, encoder=JSONEncoder)
    threads = models.PositiveIntegerField(default=0)
    metrics = models.JSONField(default=dict, encoder=JSONEncoder)  # extra metrics

    class Meta:
        db_table = 'utilmeta_worker_monitor'
        ordering = ('time',)

    @classmethod
    def current(cls) -> Optional['WorkerMonitor']:
        return cls.objects.last()   # already order by time


class InstanceMonitor(SystemMetrics, ServiceMetrics):
    time = models.DateTimeField(default=time_now)
    layer = models.PositiveSmallIntegerField(default=0)
    interval = models.PositiveIntegerField(default=None, null=True)  # in seconds

    instance = models.ForeignKey(Resource, related_name='instance_metrics', on_delete=models.CASCADE)
    threads = models.PositiveIntegerField(default=0)

    current_workers = models.PositiveIntegerField(default=0)

    avg_worker_lifetime = models.PositiveBigIntegerField(default=None, null=True)
    new_spawned_workers = models.PositiveBigIntegerField(default=0)
    avg_workers = models.DecimalField(default=None, null=True, max_digits=10, decimal_places=2)

    metrics = models.JSONField(default=dict, encoder=JSONEncoder)   # extra metrics

    class Meta:
        db_table = 'utilmeta_instance_monitor'
        ordering = ('time',)


class DatabaseMonitor(models.Model):
    objects = models.Manager()

    time = models.DateTimeField(default=time_now)
    layer = models.PositiveSmallIntegerField(default=0)
    interval = models.PositiveIntegerField(default=None, null=True)  # in seconds

    database = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='database_metrics')

    used_space = models.PositiveBigIntegerField(default=0)  # used disk space
    server_used_space = models.PositiveBigIntegerField(default=0)  # used disk space
    active_connections = models.PositiveBigIntegerField(default=0)
    current_connections = models.PositiveBigIntegerField(default=0)
    server_connections = models.PositiveBigIntegerField(default=0)

    new_transactions = models.PositiveBigIntegerField(default=0)

    metrics = models.JSONField(default=dict, encoder=JSONEncoder)

    queries_num = models.PositiveBigIntegerField(default=0)
    qps = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True)
    query_avg_time = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    operations = models.JSONField(default=dict, encoder=JSONEncoder)  # {'SELECT': 100, 'UPDATE': 21, ...}

    class Meta:
        db_table = 'utilmeta_database_monitor'
        ordering = ('time',)


class CacheMonitor(models.Model):
    objects = models.Manager()

    time = models.DateTimeField(default=time_now)
    layer = models.PositiveSmallIntegerField(default=0)
    interval = models.PositiveIntegerField(default=None, null=True)  # in seconds

    cache = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='cache_metrics')

    cpu_percent = models.DecimalField(max_digits=6, decimal_places=2, default=None, null=True)
    memory_percent = models.DecimalField(max_digits=6, decimal_places=2, default=None, null=True)
    used_memory = models.PositiveBigIntegerField(default=0)
    file_descriptors = models.PositiveIntegerField(default=None, null=True)
    open_files = models.PositiveBigIntegerField(default=None, null=True)
    # used_memory = PositiveBigIntegerField(default=0)
    current_connections = models.PositiveBigIntegerField(default=0)
    total_connections = models.PositiveBigIntegerField(default=0)
    qps = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True)

    metrics = models.JSONField(default=dict, encoder=JSONEncoder)

    class Meta:
        db_table = 'utilmeta_cache_monitor'
        ordering = ('time',)


class WebMixin(models.Model):
    """
        Log data using http/https schemes
    """
    scheme = models.CharField(default=None, null=True, max_length=20)
    method = models.CharField(default=None, null=True, max_length=20)
    # replace the unit property
    request_type = models.CharField(max_length=200, default=None, null=True)
    response_type = models.CharField(max_length=200, default=None, null=True)
    request_headers = models.JSONField(default=dict, null=True, encoder=JSONEncoder)
    response_headers = models.JSONField(default=dict, null=True, encoder=JSONEncoder)

    user_agent = models.JSONField(default=None, null=True, encoder=JSONEncoder)
    status = models.PositiveSmallIntegerField(default=200, null=True)
    length = models.PositiveBigIntegerField(default=0, null=True)
    query = models.JSONField(default=dict, null=True, encoder=JSONEncoder)
    data = models.JSONField(null=True, default=None, encoder=JSONEncoder)
    result = models.JSONField(null=True, default=None, encoder=JSONEncoder)

    full_url = models.URLField(default=None, null=True)  # xxx://xxx/xxx?xxx
    path = models.URLField(null=True, default=None)  # replace the unit property
    # regard current server (who write logs) as target, count it's in & out
    in_traffic = models.PositiveBigIntegerField(default=0)
    out_traffic = models.PositiveBigIntegerField(default=0)
    public = models.BooleanField(default=True)
    # public request or invoke

    class Meta:
        abstract = True


class VersionLog(models.Model):
    objects = models.Manager()

    service = models.CharField(max_length=100)
    node_id = models.CharField(max_length=100, default=None, null=True, db_index=True)
    instance: Resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='restart_records')
    time: datetime = models.DateTimeField(auto_now_add=True)
    # finish_time: datetime = models.DateTimeField(default=None, null=True)
    down_time = models.PositiveBigIntegerField(default=None, null=True)     # ms
    # down time, None means no down time

    success = models.BooleanField(default=None, null=True)
    restart_data = models.JSONField(default=dict, encoder=JSONEncoder)
    # trigger_index = models.CharField(max_length=100, default=None, null=True)
    # trigger_value = models.FloatField(default=None, null=True)
    # threshold = models.FloatField(default=None, null=True)
    #
    # return_code = models.PositiveSmallIntegerField(default=None, null=True)
    # manual = models.BooleanField(default=False)
    # success = models.BooleanField(default=None, null=True)
    # reload = models.BooleanField(default=False)
    # method = models.CharField(max_length=40, null=True, default=None)
    # like chain-reload. zerg-dance supported by the wsgi backend

    # info = models.JSONField(default=dict)

    version = models.CharField(max_length=100)
    remote_id = models.CharField(max_length=100, default=None, null=True)

    class Meta:
        db_table = 'utilmeta_version_log'

    # @property
    # def message(self):
    #     man_str = 'Manual' if self.manual else 'Automatic'
    #     type = 'task' if self.instance.task else 'service'
    #     restart = 'reload' if self.reload else 'restart'
    #     due = f' due to [{self.trigger_index} > {self.threshold}]' \
    #           f' (={self.trigger_value})' if self.trigger_value else ''
    #     ident = f'[{self.instance.service}]({self.instance.server.ip})'
    #     return f'{man_str} triggered {type} instance {ident} {restart}' \
    #            f'{due} at {self.time.strftime(DateFormat.DATETIME)}'


class AlertType(models.Model):
    service = models.CharField(max_length=100)
    node_id = models.CharField(max_length=100, default=None, null=True, db_index=True)
    category = models.CharField(max_length=40)
    level = models.CharField(max_length=40)

    settings_id = models.CharField(max_length=40, default=None, null=True)
    # settings: AlertSettings = OneToOneField(
    #     AlertSettings, on_delete=SET_NULL, default=None, null=True, related_name='alert_type')
    threshold = models.FloatField(default=None, null=True)
    # for downgrade types, configurable

    subcategory = models.CharField(max_length=200)
    name = models.CharField(max_length=100)   # settings name or custom name
    target = models.TextField()
    # eg
    # type.category: resource_saturated
    # type.subcategory: cpu_percent_exceed
    # type.name: cpu_percent > 80

    # type.category: service_downgrade
    # type.subcategory: slow_response
    # type.name: Slow response at POST /api/user

    ident = models.CharField(max_length=500)

    compress_window: int = models.PositiveBigIntegerField(null=True, default=None)   # seconds
    min_times: int = models.PositiveIntegerField(default=1)

    resource = models.ForeignKey(
        Resource, on_delete=models.SET_NULL,
        null=True, default=None, related_name='alert_types',
    )

    created_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'utilmeta_alert_type'
        unique_together = ('service', 'ident')

    # @classmethod
    # def get(cls, ident: str) -> Optional['AlertSettings']:
    #     from utilmeta.conf import config
    #     return cls.objects.filter(service_id=config.name, ident=ident).first()


class AlertLog(models.Model):
    objects = models.Manager()

    type: AlertType = models.ForeignKey(AlertType, on_delete=models.CASCADE, related_name='alert_logs')
    server: Resource = models.ForeignKey(
        Resource, on_delete=models.CASCADE,
        related_name='server_alert_logs', default=None, null=True,
    )
    instance: Resource = models.ForeignKey(
        Resource, on_delete=models.CASCADE,
        related_name='instance_alert_logs', default=None, null=True,
    )
    version = models.ForeignKey(
        VersionLog, related_name='alert_logs',
        on_delete=models.SET_NULL, null=True, default=None,
    )

    # impact_requests = models.PositiveBigIntegerField(default=None, null=True)
    # impact_users = models.PositiveIntegerField(default=None, null=True)
    # impact_ips = models.PositiveIntegerField(default=None, null=True)
    # impact services / tasks can be interfere from [server] field

    relieved_time = models.DateTimeField(default=None, null=True)
    # relieved_time=None (opening alert) are open for new count

    # trigger_times: list = fields.ArrayField(models.DateTimeField(), default=list)
    # trigger_values: list = fields.ArrayField(models.FloatField(), default=list)

    trigger_times = models.JSONField(default=list, encoder=JSONEncoder)
    trigger_values = models.JSONField(default=list, encoder=JSONEncoder)

    # [dict(value=<SOME_VALUE>, time=<SOME_TIME>), ...]
    time = models.DateTimeField(default=time_now)
    # start time (first alert trigger time)
    latest_time: datetime = models.DateTimeField(default=time_now)
    # latest time (latest alert trigger time)

    # current_count = PositiveBigIntegerField(default=1)
    count = models.PositiveBigIntegerField(default=1)
    # message = models.TextField(default='')     # brief message to notify
    data = models.JSONField(default=None, null=True, encoder=JSONEncoder)

    class Meta:
        db_table = 'utilmeta_alert_log'

    @classmethod
    def get(cls, id) -> Optional['AlertLog']:
        if not id:
            return None
        return cls.objects.filter(id=id).first()

    @property
    def uncertain(self):
        return self.count < self.type.min_times

    @property
    def compressible(self):
        if not self.type.compress_window:
            return False
        return (time_now() - self.latest_time).total_seconds() < self.type.compress_window

    def relieve(self):
        if self.relieved_time:
            return True
        if self.uncertain:
            # only append relieve times so the alert is still open
            self.delete()
            return True
        self.relieved_time = time_now()
        self.save(update_fields=['relieved_time'])
        return self.compressible        # only report legit relieve


class ServiceLog(WebMixin):
    objects = models.Manager()

    id = models.BigAutoField(primary_key=True)

    service = models.CharField(max_length=100)
    node_id = models.CharField(max_length=100, default=None, null=True, db_index=True)
    # supervisor.remote_id
    # node.id (in the supervisor)
    # global identifier

    version = models.ForeignKey(
        VersionLog, related_name='service_logs',
        on_delete=models.SET_NULL, null=True, default=None,
    )
    instance = models.ForeignKey(
        Resource, related_name='instance_logs',
        on_delete=models.SET_NULL, null=True, default=None,
    )
    endpoint = models.ForeignKey(
        Resource, on_delete=models.SET_NULL,
        null=True, default=None, related_name='endpoint_logs',
    )
    # incase the endpoint not loaded yet
    endpoint_ident = models.CharField(max_length=200, default=None, null=True)
    endpoint_ref = models.CharField(max_length=200, default=None, null=True)

    # add redundant field endpoint_ident to make a quick query index and remain even after endpoint is deleted
    # endpoint_ident = models.CharField(max_length=200, null=True, default=None, db_index=True)
    # endpoint_path = URLField(default=None, null=True)
    # units = ArrayField(CharField(max_length=10), default=list)
    # the orders that the process unit is called
    worker = models.ForeignKey(
        Worker, related_name='logs',
        on_delete=models.SET_NULL, null=True, default=None,
    )
    # -----

    level = models.CharField(max_length=30)
    # volatile log will be deleted when it is not count by any aggregates
    time = models.DateTimeField()  # not auto_now_add, cache stored log may add after request for some time
    duration = models.PositiveBigIntegerField(default=None, null=True)
    # for http requests duration is the time between server receive request and send response
    # for ws requests duration is the time between client open a ws connection and close it
    thread_id = models.PositiveBigIntegerField(default=None, null=True)
    # thread id that handle this request / invoke

    user_id = models.CharField(max_length=100, null=True, default=None, db_index=True)
    # referrer = URLField(default=None, null=True)
    ip = models.GenericIPAddressField()

    trace = models.JSONField(default=list, encoder=JSONEncoder)
    messages = models.JSONField(default=list, encoder=JSONEncoder)

    alert = models.ForeignKey(
        'AlertLog', related_name='service_logs',
        on_delete=models.SET_NULL, null=True, default=None,
    )

    volatile = models.BooleanField(default=True)
    # deleted_time = models.DateTimeField(default=None, null=True)
    # ----------
    supervisor = models.ForeignKey(
        Supervisor, related_name='logs', on_delete=models.SET_NULL,
        default=None, null=True,
    )
    access_token = models.ForeignKey(
        AccessToken, related_name='logs', on_delete=models.SET_NULL,
        default=None, null=True,
    )

    class Meta:
        db_table = 'utilmeta_service_log'


class RequestLog(WebMixin):
    objects = models.Manager()

    id = models.BigAutoField(primary_key=True)
    service = models.CharField(max_length=100)
    node_id = models.CharField(max_length=100, default=None, null=True, db_index=True)

    # volatile = models.BooleanField(default=True)
    # requests made in other service request context
    time = models.DateTimeField()  # not auto_now_add, cache stored log may add after request for some time
    # version = models.ForeignKey(
    #     VersionLog, related_name='service_logs',
    #     on_delete=models.SET_NULL, null=True, default=None
    # )

    duration = models.PositiveBigIntegerField(default=None, null=True)
    worker = models.ForeignKey(
        Worker, related_name='request_logs',
        on_delete=models.SET_NULL, null=True, default=None,
    )

    context_type = models.CharField(max_length=40, default=None, null=True)
    # request
    context_id = models.CharField(max_length=200, default=None, null=True)
    # log id / execution id

    host = models.URLField(default=None, null=True)      # host of the requested host (ip or domain name)

    remote_log = models.TextField(default=None, null=True)     # able to supply other type ident (eg. uuid)
    # remote utilmeta log id (in target service) to support recursive tracing

    asynchronous = models.BooleanField(default=None, null=True)
    timeout = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True)
    # SINGLE REQUEST, RETIRES NOT INCLUDED

    timeout_error = models.BooleanField(default=False)     # request is timeout
    server_error = models.BooleanField(default=False)     # ssl cert error when query the target host
    client_error = models.BooleanField(default=False)     # ssl cert error when query the target host
    ssl_error = models.BooleanField(default=False)     # ssl cert error when query the target host
    dns_error = models.BooleanField(default=False)

    alert = models.ForeignKey(
        AlertLog, related_name='request_logs',
        on_delete=models.SET_NULL, null=True, default=None,
    )

    class Meta:
        db_table = 'utilmeta_request_log'


class QueryLog(models.Model):
    objects = models.Manager()

    # SLOW or error db query log
    id = models.BigAutoField(primary_key=True)
    time = models.DateTimeField()
    # version = models.ForeignKey(
    #     VersionLog, related_name='service_logs',
    #     on_delete=models.SET_NULL, null=True, default=None
    # )
    database = models.ForeignKey(
        Resource, on_delete=models.CASCADE,
        related_name='database_query_logs',
    )
    model = models.ForeignKey(
        Resource, on_delete=models.SET_NULL, default=None, null=True,
        related_name='model_query_logs'
    )
    query = models.TextField()
    duration = models.PositiveBigIntegerField(default=None, null=True)  # ms
    message = models.TextField(default='')
    worker = models.ForeignKey(
        Worker, related_name='query_logs', on_delete=models.SET_NULL,
        null=True, default=None,
    )

    operation = models.CharField(max_length=32, default=None, null=True)
    tables = models.JSONField(default=list, encoder=JSONEncoder)

    context_type = models.CharField(max_length=40, default=None, null=True)
    # request
    context_id = models.CharField(max_length=200, default=None, null=True)
    # log id / execution id

    alert = models.ForeignKey(
        AlertLog, related_name='query_logs',
        on_delete=models.SET_NULL, null=True, default=None,
    )

    class Meta:
        db_table = 'utilmeta_query_log'


class AggregationLog(models.Model):
    objects = models.Manager()

    service = models.CharField(max_length=100)
    node_id = models.CharField(max_length=100, default=None, null=True, db_index=True)
    supervisor = models.ForeignKey(
        Supervisor, related_name='aggregation_logs', on_delete=models.SET_NULL,
        default=None, null=True,
    )
    data = models.JSONField(default=dict, encoder=JSONEncoder)

    # report the aggregated analytics from log from time span
    layer = models.PositiveSmallIntegerField(default=0)
    # 0: hourly
    # 1: daily
    # 2: monthly

    from_time = models.DateTimeField()
    to_time = models.DateTimeField()
    date = models.DateField(default=None, null=True)

    created_time = models.DateTimeField(auto_now_add=True)
    reported_time = models.DateTimeField(default=None, null=True)
    error = models.TextField(default=None, null=True)
    remote_id = models.CharField(max_length=40, default=None, null=True)
    # remote id is not None means the report is successful

    class Meta:
        db_table = 'utilmeta_aggregation_log'


supervisor_related_models = [
    Resource,
    AlertType,
    ServiceLog,
    RequestLog,
    VersionLog,
    AggregationLog,
]
