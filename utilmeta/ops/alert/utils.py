from utype.types import *
from utilmeta.ops.schema import SupervisorAlertSettingsSchema

# process-level caches
# _alert_metrics: List['AlertMetric'] = []
# _alert_events: List['AlertEvent.EventSettings'] = []


class AlertCategory:
    unavailable = 'unavailable'   # down (unavailable)
    disconnected = 'disconnected'
    error = 'error'
    downgrade = 'downgrade'
    load_surge = 'load_surge'
    resource_exhaustion = 'resource_exhaustion'
    dependency_failure = 'dependency_failure'
    security = 'security'
    data_corruption = 'data_corruption'


class ResourceType:
    api = 'api'
    task = 'task'
    server = 'server'
    instance = 'instance'
    worker = 'worker'
    database = 'database'
    cache = 'cache'

