from utype.types import *
from django.db import models
from utilmeta.utils import time_now
from typing import TYPE_CHECKING, Optional, Callable
from utilmeta.ops.schema import AlertSettingsParams
from utilmeta.ops.res.event import BaseEvent, BaseEventRegistry, event_handler
from .utils import ResourceType, AlertCategory
from utilmeta.utils import adapt_async, awaitable
import inspect


if TYPE_CHECKING:
    from utilmeta.ops.models import Resource, AlertLog


def alert_event(
    resource_type: str = None,
    description: str = None,
    default_severity: int = None,
    category: str = None,
    silent: bool = False,
    source=None,
):
    return event_handler(**locals(), event_cls=AlertEvent)


class AlertEventSettings:
    def __init__(
        self,
        evt: "AlertEvent",
        settings: AlertSettingsParams,
    ):
        self.evt = evt
        if settings.severity is None:
            settings.severity = evt.default_severity
        self.settings = settings

    @property
    def settings_data(self):
        return self.settings.get_settings_data()

    @property
    def settings_id(self):
        return self.settings.id

    def match_target(self, target: Union[str, 'Resource'] = None):
        return self.settings.match_target(target)


class AlertEvent(BaseEvent):
    DEFAULT_SEVERITY = 2
    event_settings_cls = AlertEventSettings

    def __init__(self, handler: Callable, **kwargs):
        super().__init__(handler, **kwargs)
        self._settings: List[AlertEventSettings] = []

    def add_settings(self, settings: AlertEventSettings):
        for item in self._settings:
            if item.settings_id == settings.settings_id:
                return
        self._settings.append(settings)

    def get_settings(self, target: Union[str, 'Resource'] = None) -> Optional[AlertEventSettings]:
        # whether to alert
        for item in self._settings:
            if item.match_target(target):
                return item
        if self.default_severity == 0:
            # P0: critical event, alert anyway
            return self.event_settings_cls(
                self,
                settings=AlertSettingsParams(
                    severity=self.default_severity,
                    target_id=target.pk if target else None,
                    target_ident=target.ident if target else None,
                )
            )
        return None

    def __call__(
        self,
        target: Union[str, 'Resource'] = None,
        triggered_time: datetime = None,
        force_alarm: bool = False,
        **kwargs
    ) -> Optional["AlertLog"]:
        if self.handler(**kwargs):
            # not triggering
            return None

        from utilmeta import service
        from utilmeta.ops.store import store
        from .config import Alert

        alert = Alert.config()
        if not alert:
            return None

        settings = self.get_settings(target)

        if not settings:
            return None

        event_id = None
        triggered_time = triggered_time or time_now()
        if target and isinstance(target, str):
            target = Resource.objects.filter(
                models.Q(id=target) | models.Q(ident=target),
                service=service.name,
                node_id=store.node_id
                # deprecated=False,
            ).first()
            if not target:
                event_id = target

        return alert.trigger(
            target=target,
            settings=settings.settings,
            # if settings else AlertSettingsParams(
            #     severity=self.default_severity,
            #     silent=bool(self.default_severity)
            #     # do not notify if settings not exists
            # ),
            name=self.name,
            triggered_time=triggered_time,
            triggered_value=True,
            event_id=event_id,
            data=kwargs,
            force_alarm=force_alarm,
        )

    @awaitable(__call__)
    async def __call__(
        self,
        target: Union[str, 'Resource'] = None,
        triggered_time: datetime = None,
        force_alarm: bool = False,
        **kwargs
    ) -> Optional["AlertLog"]:
        r = self.handler(**kwargs)
        if inspect.isawaitable(r):
            r = await r
        if r:
            # not triggering
            return None

        from utilmeta import service
        from utilmeta.ops.config import Operations
        from utilmeta.ops.store import store
        from .config import Alert

        config = Operations.config()
        alert = Alert.config()
        if not alert:
            return None

        settings = self.get_settings(target)

        if not settings:
            return None

        event_id = None
        triggered_time = triggered_time or time_now()
        if target and isinstance(target, str):
            target = Resource.objects.filter(
                models.Q(id=target) | models.Q(ident=target),
                service=service.name,
                node_id=store.node_id
                # deprecated=False,
            ).first()
            if not target:
                event_id = target

        trigger_func = adapt_async(alert.trigger, close_conn=config.db_alias)
        return trigger_func(
            target=target,
            settings=settings.settings,
            # if settings else AlertSettingsParams(
            #     severity=self.default_severity,
            #     silent=bool(self.default_severity)
            #     # do not notify if settings not exists
            # ),
            name=self.name,
            triggered_time=triggered_time,
            triggered_value=True,
            event_id=event_id,
            data=kwargs,
            force_alarm=force_alarm,
        )


class AlertEventRegistry(BaseEventRegistry):
    @alert_event(
        resource_type=ResourceType.api,
        default_severity=2,
    )
    def api_4xx_response(self, *args,
                         method: str,
                         url: str,
                         status: int,
                         result=None,
                         user_id=None,
                         brief_message: str = None,
                         ): pass

    @alert_event(
        resource_type=ResourceType.api,
        category=AlertCategory.error,
        default_severity=1
    )
    def api_5xx_response(self, *args,
                         method: str,
                         url: str,
                         status: int,
                         result=None,
                         user_id=None,
                         brief_message: str = None,
                         ): pass

    @alert_event(
        resource_type=ResourceType.api,
        category=AlertCategory.dependency_failure,
        default_severity=2
    )
    def api_error_outbound_request(self, *args,
                                   method: str,
                                   url: str,
                                   status: int): pass

    @alert_event(
        resource_type=ResourceType.api,
        category=AlertCategory.dependency_failure,
        default_severity=2
    )
    def api_timeout_outbound_request(self, *args,
                                     method: str,
                                     url: str,
                                     status: int): pass

    @alert_event(
        category=AlertCategory.error,
        resource_type=ResourceType.task,
        default_severity=1
    )
    def task_execution_failed(self): pass

    @alert_event(
        category=AlertCategory.error,
        resource_type=ResourceType.task,
        default_severity=1
    )
    def task_execution_timeout(self): pass

    @alert_event(
        category=AlertCategory.error,
        resource_type=ResourceType.instance,
        default_severity=2
    )
    def ops_cycle_failed(self, *args, event_type: str): pass

    @alert_event(
        category=AlertCategory.error,
        resource_type=ResourceType.instance,
        default_severity=1
    )
    def alert_check_failed(
        self,
        *args,
        settings_name: str,
        settings: dict = None,
        error: str = None,
        message: str = ''
    ): pass

    @alert_event(
        category=AlertCategory.error,
        resource_type=ResourceType.instance,
        default_severity=2
    )
    def report_metric_failed(
        self,
        *args,
        metric_name: str,
        metric_ref: str,
        to_time: datetime = None,
        error: str = None,
        message: str = ''
    ): pass

    @alert_event(
        category=AlertCategory.unavailable,
        resource_type=ResourceType.instance,
        default_severity=0
    )
    def service_instance_unavailable(self): pass

    @alert_event(
        category=AlertCategory.unavailable,
        resource_type=ResourceType.database,
        default_severity=0
    )
    def database_instance_unavailable(self): pass

    @alert_event(
        category=AlertCategory.unavailable,
        resource_type=ResourceType.cache,
        default_severity=0
    )
    def cache_instance_unavailable(self): pass

    @alert_event(
        category=AlertCategory.dependency_failure,
        resource_type=ResourceType.instance,
        default_severity=2
    )
    def supervisor_request_failed(
        self, *args,
        request_type: str,
        alert_id: int = None,
        aggregation_log_id: int = None,
        data: dict = None,
        response_status: int = None,
        response_data=None,
    ): pass

    # --- inform

    @alert_event(
        resource_type=ResourceType.instance,
        default_severity=3
    )
    def service_instance_restarted(self): pass


event = AlertEventRegistry()
