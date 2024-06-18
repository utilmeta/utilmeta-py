from .log import LogLevel
from django.db import models
from utilmeta.utils import replace_null, ignore_errors, AgentOS, AgentDevice, AgentBrowser, fast_digest
from django.db.utils import DatabaseError
from django.core.exceptions import FieldError
from utype.types import *
from django.db.models.functions import TruncSecond


def user_comp_hash(user_id):
    return fast_digest(
        str(user_id),
        compress=True,
        case_insensitive=False,
        consistent=True,
        mod=2 ** 24
    )


def get_agent_dist(logs: models.QuerySet, exists: bool = False):
    # service logs
    try:
        os_dist = {}
        browser_dist = {}
        device_dist = {}
        for os in AgentOS.gen():
            qs = logs.filter(user_agent__os__icontains=os)
            num = qs.exists() if exists else qs.count()
            if num:
                os_dist[os] = num
        for br in AgentBrowser.gen():
            qs = logs.filter(user_agent__browser__icontains=br)
            num = qs.exists() if exists else qs.count()
            if num:
                browser_dist[br] = num
        for device in AgentDevice.gen():
            qs = logs.filter(user_agent__device=device)
            num = qs.exists() if exists else qs.count()
            if num:
                device_dist[device] = num
        return dict(
            os_dist=os_dist,
            browser_dist=browser_dist,
            device_dist=device_dist
        )
    except (DatabaseError, FieldError):
        # raise FieldError when json key lookup is not supported
        return {}


def aggregate_endpoint_logs(service: str, to_time: datetime, layer: int = 0):
    from .log import _endpoints_map
    result = {}
    for ident, endpoint in _endpoints_map.items():
        if not endpoint.remote_id:
            continue
        data = aggregate_logs(
            service=service,
            to_time=to_time,
            layer=layer,
            endpoint_ident=ident
        )
        if data:
            result[endpoint.remote_id] = data
    return result


def aggregate_logs(service: str,
                   to_time: datetime,
                   layer: int = 0,
                   include_users: Union[bool, int] = False,
                   include_ips: Union[bool, int] = False,
                   endpoint_ident: str = None):

    timespan = [timedelta(hours=1), timedelta(days=1)][layer]
    start = to_time - timespan
    current = to_time
    seconds = timespan.total_seconds()
    # gte ~ lt only apply to layer0, in upper layer it's gt ~ lte

    from .models import ServiceLog, WorkerMonitor
    query = dict(
        service=service,
        time__gte=start,
        time__lt=current
    )
    if endpoint_ident:
        query.update(endpoint_ident=endpoint_ident)

    service_logs = ServiceLog.objects.filter(**query)

    if endpoint_ident or layer:
        total_data = service_logs.aggregate(
            requests=models.Count('id'),
            avg_time=models.Avg('duration'),
        )
        total_requests = requests = total_data.get('requests') or 0
        avg_time = total_data.get('avg_time') or 0
    else:
        worker_qs = WorkerMonitor.objects.filter(
            worker__instance__service=service,
            time__gte=start,
            time__lt=current
        )
        requests = service_logs.count()
        total_requests = worker_qs.aggregate(v=models.Sum('requests'))['v'] or requests
        if total_requests:
            avg_time = worker_qs.aggregate(
                v=models.Sum(models.F('avg_time') * models.F('requests')) / total_requests)['v'] or 0
        else:
            avg_time = 0

    if not total_requests:
        return

    errors = service_logs.filter(models.Q(level=LogLevel.ERROR) | models.Q(level__iexact='ERROR')).count()

    dict_values = {}
    aggregate_info = []

    if not layer:
        aggregate_info.extend([
            ('status', 'statuses', None),
            ('level', 'levels', None),
        ])
    if include_users:
        aggregate_info.append([
            ('user_id', 'user_dist', include_users)
        ])
    if include_ips:
        aggregate_info.append([
            ('ip', 'ip_dist', include_ips)
        ])

    for name, field, limit in aggregate_info:
        qs = service_logs.exclude(**{name: None}).values(
            name).annotate(count=models.Count('id'))
        if isinstance(limit, int):
            qs = qs.order_by('-count')[:limit]
        dicts = {val[name]: val['count'] for val in qs}
        if name == 'user_id':
            dicts = {user_comp_hash(k): v for k, v in dicts.items()}
        dict_values[field] = dicts

    service_logs_duration = service_logs.order_by('-duration')
    mean_time = service_logs_duration[requests // 2].duration if requests else 0
    p95_time = service_logs_duration[requests // 20].duration if requests else 0
    p99_time = service_logs_duration[requests // 100].duration if requests else 0
    p999_time = service_logs_duration[requests // 1000].duration if requests else 0

    if layer:
        return dict(
            mean_time=mean_time,
            p95_time=p95_time,
            p99_time=p99_time,
            p999_time=p999_time,
            **dict_values,
            **replace_null(service_logs.aggregate(
                time_stddev=models.StdDev('duration'),
                uv=models.Count('user_id', distinct=True),
                ip=models.Count('ip', distinct=True),
            )),
        )

    agent_dist = get_agent_dist(service_logs) if not endpoint_ident else {}

    # get MAX RPS
    max_rps = (
        service_logs.annotate(
            second=TruncSecond('time')
        )
        .values('second')
        .annotate(request_count=models.Count('id'))
        .values_list('request_count', flat=True)
        .order_by('-request_count')
        .first()
    )

    return dict(
        requests=total_requests,
        avg_time=avg_time,
        errors=errors,
        rps=round(total_requests / seconds, 2),
        mean_time=mean_time,
        p95_time=p95_time,
        p99_time=p99_time,
        p999_time=p999_time,
        max_rps=max_rps,
        **agent_dist,
        **dict_values,
        **replace_null(service_logs.aggregate(
            in_traffic=models.Sum('in_traffic'),
            out_traffic=models.Sum('out_traffic'),
            time_stddev=models.StdDev('duration'),
            uv=models.Count('user_id', distinct=True),
            ip=models.Count('ip', distinct=True),
        )),
    )
