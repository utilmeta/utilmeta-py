from utilmeta.utils import (
    time_now,
    ignore_errors,
    replace_null,
)
from django.db import models
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utilmeta.ops.models import Worker


class WorkerMetricsLogger:
    def __init__(self):
        # common metrics
        self._total_in = 0
        self._total_out = 0
        self._total_outbound_requests = 0
        self._total_outbound_request_time = 0
        self._total_outbound_errors = 0
        self._total_outbound_timeouts = 0

        # request metrics
        self._total_requests = 0
        self._total_errors = 0
        self._total_time = 0

    @ignore_errors
    def log(
        self,
        duration: float,
        in_traffic: int = 0,
        out_traffic: int = 0,
        outbound: bool = False,
        error: bool = False,
        timeout: bool = False,
    ):
        self._total_in += in_traffic
        self._total_out += out_traffic

        if outbound:
            self._total_outbound_requests += 1
            self._total_outbound_errors += 1 if error else 0
            self._total_outbound_timeouts += 1 if timeout else 0
            self._total_outbound_request_time += duration
        else:
            self._total_requests += 1
            self._total_errors += 1 if error else 0
            self._total_time += duration

    def reset(self):
        self._total_requests = 0
        self._total_errors = 0
        self._total_time = 0
        self._total_in = 0
        self._total_out = 0
        self._total_outbound_requests = 0
        self._total_outbound_request_time = 0
        self._total_outbound_errors = 0
        self._total_outbound_timeouts = 0

    def fetch(self, interval: int):
        if not self._total_requests:
            return dict()
        return dict(
            requests=self._total_requests,
            in_traffic=self._total_in,
            out_traffic=self._total_out,
            avg_time=self._total_time / self._total_requests,
            rps=self._total_requests / interval,
            errors=self._total_errors,
            outbound_requests=self._total_outbound_requests,
            outbound_avg_time=(
                self._total_outbound_request_time / self._total_outbound_requests
            )
            if self._total_outbound_requests
            else 0,
            outbound_rps=self._total_outbound_requests / interval,
            outbound_errors=self._total_outbound_errors,
            outbound_timeouts=self._total_outbound_timeouts,
        )

    @ignore_errors(default=dict)  # ignore cache errors
    def retrieve(self, time: datetime) -> dict:
        now = time_now()
        requests = self._total_requests
        in_traffic = self._total_in
        out_traffic = self._total_out
        total_time = self._total_time
        errors = self._total_errors
        outbound_requests = self._total_outbound_requests
        total_outbound_request_time = self._total_outbound_request_time
        outbound_errors = self._total_outbound_errors
        outbound_timeouts = self._total_outbound_timeouts

        values = dict(
            time=now,
        )
        if requests:
            values.update(
                requests=models.F("requests") + requests,
                rps=round(requests / (now - time).total_seconds(), 4),
                avg_time=(
                    (models.F("avg_time") * models.F("requests") + total_time)
                    / (models.F("requests") + requests)
                )
                if requests
                else models.F("avg_time"),
                errors=models.F("errors") + errors,
            )
        if in_traffic:
            values.update(in_traffic=models.F("in_traffic") + in_traffic)
        if out_traffic:
            values.update(out_traffic=models.F("out_traffic") + out_traffic)
        if outbound_requests:
            values.update(
                outbound_requests=models.F("outbound_requests") + outbound_requests,
                outbound_errors=models.F("outbound_errors") + outbound_errors,
                outbound_timeouts=models.F("outbound_timeouts") + outbound_timeouts,
                outbound_rps=round(
                    outbound_requests / (now - time).total_seconds(), 4
                ),
                outbound_avg_time=(
                    (
                        models.F("outbound_requests") * models.F("outbound_avg_time")
                        + total_outbound_request_time
                    )
                    / (models.F("outbound_requests") + outbound_requests)
                )
                if outbound_requests
                else models.F("outbound_avg_time"),
            )

        return replace_null(values)

    def save(self, inst: "Worker", **kwargs):
        values = self.retrieve(inst.time)
        kwargs.update(values)
        self.reset()
        inst.__class__.objects.filter(pk=inst.pk).update(**kwargs)
        return values

    def update_worker(self, worker: "Worker", record: bool = False, interval: int = None):
        from utilmeta.ops.models import Worker, WorkerMonitor
        if not isinstance(worker, Worker):
            return
        now = time_now()
        sys_metrics = worker.get_sys_metrics()
        req_metrics = self.fetch(
            interval or max(1.0, (now - worker.time).total_seconds())
        )
        self.save(worker, **sys_metrics, connected=True, time=now)
        if record:
            WorkerMonitor.objects.create(
                worker=worker,
                interval=interval,
                time=now,
                **sys_metrics,
                **req_metrics,
            )
