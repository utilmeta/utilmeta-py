import threading
from utilmeta.core.response import Response
from utilmeta.core.request import var, Request
from utilmeta.core.server import ServiceMiddleware
from typing import TYPE_CHECKING
from utilmeta.ops.store import store

if TYPE_CHECKING:
    from utilmeta.ops import Operations


class LogMiddleware(ServiceMiddleware):
    def __init__(self, config: "Operations"):
        super().__init__(config=config)
        self.config = config

    def process_request(self, request: Request):
        # log = request_logger.setup(request)
        # log.set(Logger())   # set logger
        logger = self.config.logger_cls()
        store.logger.set(logger)
        logger.setup_request(request)
        store.request_logger.setter(request, logger)

    def is_excluded(self, response: Response):
        request = response.request
        if request:
            if self.config.log.exclude_methods:
                if (
                    request.adaptor.request_method.upper()
                    in self.config.log.exclude_methods
                ):
                    return True
            if self.config.log.exclude_request_headers:
                if any(
                    h in self.config.log.exclude_request_headers
                    for h in request.headers
                ):
                    return True
        else:
            return True
        if self.config.log.exclude_statuses:
            if response.status in self.config.log.exclude_statuses:
                return True
        if self.config.log.exclude_response_headers:
            if any(
                h in self.config.log.exclude_response_headers for h in response.headers
            ):
                return True
        return False

    def process_response(self, response: Response):
        logger = store.logger.get(None)
        if not logger:
            return response.close()
        if not response.request:
            return response.close()

        logger.exit()
        logger.setup_response(response)

        # log metrics into current worker
        # even if the request is omitted
        store.worker_logger.log(
            duration=response.duration_ms,
            error=response.status >= 500,
            in_traffic=response.request.traffic,
            out_traffic=response.traffic,
        )

        if logger.omitted:
            return response.close()

        if self.is_excluded(response) or logger.events_only:
            if response.success and logger.vacuum:
                return response.close()

        store.responses_queue.append(response)

        if len(store.responses_queue) >= self.config.max_backlog:
            threading.Thread(target=batch_save_logs, kwargs=dict(close=True)).start()

    # def handle_error(self, error: Error, response=None):
    #     logger: Logger = _logger.get(None)
    #     if not logger:
    #         raise error.throw()
    #     logger.commit_error(error)


def batch_save_logs(close: bool = False):
    from utilmeta.ops.models import ServiceLog, QueryLog, RequestLog
    from utilmeta.core.auth import User
    from utilmeta.ops.store import store
    from .logger import Logger

    with threading.Lock():
        queue = store.responses_queue
        _responses_queue = []
        # ----------------
        logs_creates = []
        logs_bulk_creates = []
        logs_updates = []
        query_logs = []
        request_logs = []
        context_map = {}
        user_last_logs = {}

        if not store.ready:
            # not setup yet
            store.setup()
        else:
            store.load_supervisor()
            # reload supervisor

        for response in queue:
            response: Response
            try:
                logger: Logger = store.request_logger.getter(response.request)
                if not logger:
                    continue

                service_log = logger.generate_log(response)

                if not service_log:
                    continue

                context_request_logs = logger.generate_request_logs(
                    context_type='service_log',
                    context_id=service_log.id
                )

                if service_log.id:
                    logs_updates.append(service_log)
                else:
                    if context_request_logs:
                        context_map[service_log] = context_request_logs
                        request_logs.extend(context_request_logs)
                        logs_creates.append(service_log)
                    else:
                        logs_bulk_creates.append(service_log)

                if service_log.user_id:
                    user_config = var.user_config.getter(response.request)

                    if isinstance(user_config, User) and user_config.last_activity_field:
                        user_last_logs.setdefault(user_config, {}).update({service_log.user_id: service_log.time})

            finally:
                response.close()

        if not logs_creates and not logs_bulk_creates and not logs_updates:
            return

        if logs_updates:
            for log in logs_updates:
                log.save()

        if logs_bulk_creates:
            ServiceLog.objects.bulk_create(logs_bulk_creates, ignore_conflicts=True)

        if logs_creates:
            for log in logs_creates:
                log.save()
                context_logs = context_map.get(log)
                if context_logs and log.pk:
                    # set context ID
                    for ctx_log in context_logs:
                        ctx_log.context_id = log.pk

        if query_logs:
            QueryLog.objects.bulk_create(query_logs, ignore_conflicts=True)

        if request_logs:
            RequestLog.objects.bulk_create(request_logs, ignore_conflicts=True)

        if user_last_logs:
            for user_config, user_logs in user_last_logs.items():
                user_config: User
                updates = []
                for user_id, dt in user_logs.items():
                    updates.append(user_config.user_model.init_instance(
                        user_id, **{user_config.last_activity_field: dt}))
                if updates:
                    try:
                        user_config.user_model.query().bulk_update(updates, fields=[user_config.last_activity_field])
                    except Exception as e:
                        print(f'update last_activity for: {user_config.user_model} failed: {e}')

    if close:
        from django.db import connections
        connections.close_all()

    return
