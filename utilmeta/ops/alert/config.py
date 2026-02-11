from utype.types import *
from utilmeta.conf import Config
from django.db import models
from utilmeta.utils import time_now, import_obj
from typing import Optional
from utilmeta.ops.schema import (AlertSettingsParams, EventAlertSettingsSchema, MetricAlertSettingsSchema)
from utilmeta.ops.res.metric import BaseMetric

if TYPE_CHECKING:
    from utilmeta.ops.models import Resource, AlertLog
    from .event import AlertEventSettings
    from .metric import AlertMetric


class Alert(Config):
    def __init__(
        self,
        # metric_registry: Union[str, Type[AlertMetricRegistry]] = AlertMetricRegistry,
        # event_registry: Union[str, type] = event,
        current_monitor_time_limit: int = 120,
        # default_cpu_percent_interval: int = 5,
        default_baseline_window: timedelta = timedelta(days=7),
        default_compress_window: timedelta = timedelta(hours=1),
        default_min_alarm_interval: Union[int, timedelta] = timedelta(minutes=5),
    ):
        super().__init__(locals())
        # self.metric_registry = metric_registry
        # self.event_registry = event_registry
        # self.default_cpu_percent_interval = default_cpu_percent_interval
        self.current_monitor_time_limit = current_monitor_time_limit
        self.default_baseline_window = default_baseline_window
        self.default_compress_window = default_compress_window
        self.default_min_alarm_interval = default_min_alarm_interval

    def setup_params(self, params: AlertSettingsParams):
        params.min_alarm_interval = params.min_alarm_interval if (params.min_alarm_interval
                                                                  is None) else self.default_min_alarm_interval
        params.compress_window = params.compress_window if (params.compress_window
                                                            is None) else self.default_compress_window
        return params

    def deserialize_event(self, settings: EventAlertSettingsSchema) -> Optional["AlertEventSettings"]:
        params = self.setup_params(AlertSettingsParams(settings))
        evt = import_obj(settings.event_ref)
        from .event import AlertEvent
        if not isinstance(evt, AlertEvent):
            return None
        from .event import AlertEventSettings
        settings = AlertEventSettings(
            evt,
            settings=params
        )
        evt.add_settings(settings)
        return settings

    def deserialize_metric(self, settings: MetricAlertSettingsSchema) -> Optional["AlertMetric"]:
        params = self.setup_params(AlertSettingsParams(settings))
        metric = import_obj(settings.metric_ref)
        if not isinstance(metric, BaseMetric):
            return None
        from .metric import AlertMetric
        return AlertMetric(
            metric,
            strategy=settings.strategy,
            strategy_data=settings.strategy_data,
            threshold=settings.threshold,
            exceed=settings.exceed,
            settings=params
        )

    @classmethod
    def get_log(
        cls,
        name: str,
        settings: AlertSettingsParams = None,
        target: "Resource" = None,
        event_id: str = None,
        triggered_time: datetime = None,
    ) -> Optional["AlertLog"]:
        from utilmeta.ops.models import AlertLog
        from utilmeta import service
        from utilmeta.ops.store import store
        settings = settings if isinstance(settings, AlertSettingsParams) else AlertSettingsParams.default()
        triggered_time = triggered_time or time_now()

        base_data = dict(
            service=service.name,
            node_id=store.node_id,
            supervisor=store.supervisor,
            settings_id=settings.id,
            settings_name=name,
            event_id=event_id,
            severity=settings.severity,
            target=target,
        )

        alert_log_qs = AlertLog.objects.filter(
            **base_data,
            recovered_time=None,
        )

        if settings.compress_window and not event_id:
            alert_log_qs = alert_log_qs.filter(
                latest_time__gte=triggered_time - timedelta(seconds=settings.compress_window)
            )

        alert_log: Optional[AlertLog] = alert_log_qs.order_by('-time').first()
        return alert_log

    @classmethod
    def recover(
        cls,
        settings: AlertSettingsParams,
        target=None,
        name: str = None,
        recovered_time: datetime = None,
        message: str = '',
        alert_log: "AlertLog" = None
    ):
        recovered_time = recovered_time or time_now()
        alert_log = alert_log or cls.get_log(
            name=name,
            settings=settings,
            target=target,
        )

        if not alert_log:
            return False

        if not alert_log.is_certain(
            min_times=settings.min_times,
            min_duration=settings.min_duration
        ):
            # uncertain log, just delete
            alert_log.delete()
            return True

        alert_log.recovered_time = recovered_time
        alert_log.message = message
        alert_log.save(update_fields=['recovered_time', 'message'])

        if alert_log.latest_alarm_time:
            # this alert's level is not enough for supervisor record
            # so it's not required to notify supervisor
            cls.sync_supervisor(alert_log)  # notify recovered
        return True

    @classmethod
    def trigger(
        cls,
        name: str,
        settings: AlertSettingsParams = None,
        target: "Resource" = None,
        triggered_time: datetime = None,
        triggered_value=None,
        event_id: str = None,
        data: dict = None,
        force_alarm: bool = False,
    ):
        from utilmeta.ops.models import AlertLog
        from utilmeta import service
        from utilmeta.ops.store import store
        from .event import AlertEvent
        if isinstance(name, AlertEvent):
            name = name.name

        settings = settings if isinstance(settings, AlertSettingsParams) else AlertSettingsParams.default()
        triggered_time = triggered_time or time_now()
        alert_log = cls.get_log(
            name=name,
            settings=settings,
            target=target,
            event_id=event_id,
            triggered_time=triggered_time,
        )
        if alert_log:
            values = dict(alert_log.triggered_values)
            values.update({str(triggered_time): triggered_value})
            AlertLog.objects.filter(pk=alert_log.pk).update(
                count=models.F('count') + 1,
                triggered_values=values,
                latest_time=triggered_time
            )
            alert_log.refresh_from_db(fields=['count', 'triggered_values', 'latest_time'])
        else:
            alert_log = AlertLog.objects.create(
                service=service.name,
                node_id=store.node_id,
                supervisor=store.supervisor,
                settings_id=settings.id,
                settings_name=name,
                severity=settings.severity,
                target=target,
                settings_data=settings.get_settings_data(),
                server=store.server,
                instance=store.instance,
                version=store.version,
                event_id=event_id,
                details=data,
                triggered_values={str(triggered_time): triggered_value},
            )

        if not force_alarm:
            if not alert_log.is_certain(
                min_times=settings.min_times,
                min_duration=settings.min_duration
            ):
                return alert_log

            if settings.silent:
                return alert_log

            # ALARM -----
            if settings.min_alarm_interval and alert_log.latest_alarm_time:
                if (triggered_time - alert_log.latest_alarm_time).total_seconds() < settings.min_alarm_interval:
                    return alert_log

        cls.sync_supervisor(alert_log)
        # --------
        return alert_log

    @classmethod
    def sync_supervisor(cls, alert_log: "AlertLog"):
        from utilmeta.ops.spv.client import SupervisorClient
        from utilmeta.ops.schema import AlertSchema, RecoveryEventData
        from utilmeta.ops.store import store
        from .event import event

        with SupervisorClient(
            supervisor=store.supervisor or alert_log.supervisor,
            node_id=alert_log.node_id,
            fail_silently=True,
        ) as cli:
            if alert_log.recovered_time:
                # recover alert
                resp = cli.recover_incident(
                    data=RecoveryEventData(
                        id=alert_log.remote_id,
                        alert_id=alert_log.pk,
                        recovered_time=alert_log.recovered_time.timestamp(),
                        latest_time=alert_log.latest_time.timestamp(),
                        count=alert_log.count,
                        details=alert_log.details,
                        message=alert_log.message,
                    )
                )
                if resp.success:
                    from utype.types import Datetime
                    try:
                        alert_log.remote_recovered_time = Datetime(resp.result.get('recovered_time'))
                    except TypeError:
                        alert_log.remote_recovered_time = time_now()
                    alert_log.save(update_fields=['remote_recovered_time'])
                else:
                    event.supervisor_request_failed(
                        request_type='alert/recovery',
                        alert_id=alert_log.pk,
                        data=dict(
                            alert_remote_id=alert_log.remote_id,
                        ),
                        response_status=resp.status,
                        response_data=resp.data,
                    )
            else:
                # trigger alert
                resp = cli.alert_incident(
                    data=AlertSchema(
                        time=alert_log.time.timestamp(),
                        latest_time=alert_log.latest_time.timestamp(),
                        settings_id=alert_log.settings_id,
                        settings_name=alert_log.settings_name,
                        severity=alert_log.severity,
                        target_id=alert_log.target.remote_id if alert_log.target else None,
                        event_id=alert_log.event_id,
                        count=alert_log.count,
                        details=alert_log.details,
                        impact=alert_log.impact,
                        alert_id=alert_log.pk,
                        description=alert_log.description,
                    )
                )
                if resp.success:
                    update_fields = ['latest_alarm_time']
                    alert_log.latest_alarm_time = time_now()
                    if resp.result.id:
                        if not alert_log.remote_id:
                            alert_log.remote_id = resp.result.id
                            update_fields.append('remote_id')
                    alert_log.save(update_fields=update_fields)
                else:
                    event.supervisor_request_failed(
                        request_type='alert',
                        alert_id=alert_log.pk,
                        response_status=resp.status,
                        response_data=resp.data,
                    )
