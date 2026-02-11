from utilmeta.utils import time_now, get_ref, normalize, pop
from utype.types import *
from utilmeta.ops.schema import MetricData
from functools import partial
from .base import BaseHandler

VALUE_TYPES = (int, float, Decimal)


class MetricType:
    load = 'load'
    usage = 'usage'
    duration = 'duration'
    error = 'error'
    availability = 'availability'


class AggregationType:
    avg = 'avg'
    min = 'min'
    max = 'max'
    sum = 'sum'
    p50 = 'p50'
    p95 = 'p95'
    p99 = 'p99'


class ValueType:
    numeric = 'numeric'
    count = 'count'
    percentage = 'percentage'


TIME_UNITS = ['hour', 'day', 'week', 'month', 'quarter', 'year']


class BaseMetric(BaseHandler):
    TARGET_PARAM = '__target'

    type: str = 'origin'

    def __add__(self, other: Union['BaseMetric', int, float]):
        if isinstance(self, ComputedMetric) and self.operator == 'sum':
            components = list(self.components)
        else:
            components = [ComputedMetric.Component(self)]

        if isinstance(other, ComputedMetric) and other.operator == 'sum':
            components.extend(other.components)
        elif isinstance(other, VALUE_TYPES):
            if other:
                components.append(ComputedMetric.Component(None, multiplier=float(other)))
            else:
                return self
        else:
            components.append(ComputedMetric.Component(other))
        return ComputedMetric(
            'sum',
            components=components,
            value_unit=self.value_unit,
            value_type=self.value_type
        )

    def __radd__(self, other):
        return self + other

    def __sub__(self, other: 'BaseMetric'):
        if isinstance(self, ComputedMetric) and self.operator == 'sum':
            components = list(self.components)
        else:
            components = [ComputedMetric.Component(self)]
        if isinstance(other, ComputedMetric) and other.operator == 'sum':
            components.extend([c.sub() for c in other.components])
        elif isinstance(other, VALUE_TYPES):
            if other:
                components.append(ComputedMetric.Component(None, multiplier=-float(other)))
            else:
                return self
        else:
            components.append(ComputedMetric.Component(other, multiplier=-1))
        return ComputedMetric(
            'sum',
            components=components,
            value_unit=self.value_unit,
            value_type=self.value_type
        )

    def __rsub__(self, other):
        return ComputedMetric(
            'sum',
            [ComputedMetric.Component(self, multiplier=-1)],
            value_unit=self.value_unit,
            value_type=self.value_type
        ) + other

    def __mul__(self, other: Union['BaseMetric', int, float]):
        if isinstance(other, VALUE_TYPES):
            if not other:
                return 0
            return ComputedMetric(
                'prod',
                [ComputedMetric.Component(self, multiplier=float(other))],
                value_unit=self.value_unit,
                value_type=self.value_type
            )

        if isinstance(self, ComputedMetric) and self.operator == 'prod':
            components = list(self.components)
        else:
            components = [ComputedMetric.Component(self)]

        if isinstance(other, ComputedMetric) and other.operator == 'prod':
            components.extend(other.components)
        else:
            components.append(ComputedMetric.Component(other))

        return ComputedMetric(
            'prod',
            components=components,
            value_unit=self.value_unit,
            value_type=self.value_type
        )

    def __rmul__(self, other):
        return self * other

    def __truediv__(self, other: Union['BaseMetric', int, float]):
        if isinstance(other, VALUE_TYPES):
            if not other:
                return 0
            return ComputedMetric(
                'prod',
                [ComputedMetric.Component(self, multiplier=1 / float(other))],
                value_unit=self.value_unit,
                value_type=self.value_type
            )

        if isinstance(self, ComputedMetric) and self.operator == 'prod':
            components = list(self.components)
        else:
            components = [ComputedMetric.Component(self)]

        if isinstance(other, ComputedMetric) and other.operator == 'prod':
            components.extend([c.div() for c in other.components])
        else:
            components.append(ComputedMetric.Component(other, inverse=True))

        return ComputedMetric(
            'prod',
            components=components,
            value_unit=self.value_unit,
            value_type=self.value_type
        )

    def __rtruediv__(self, other):
        if isinstance(other, ComputedMetric) and other.operator == 'prod':
            components = list(other.components)
        else:
            components = [ComputedMetric.Component(other)]

        if isinstance(self, ComputedMetric) and self.operator == 'prod':
            components.extend([c.div() for c in self.components])
        else:
            components.append([ComputedMetric.Component(self, inverse=True)])

        return ComputedMetric(
            'prod',
            components=components,
            value_unit=self.value_unit,
            value_type=self.value_type
        )

    def __init__(
        self,
        handler: Callable,
        name: str = None,
        title: str = None,
        description: str = None,
        time_unit: str = None,
        value_unit: str = None,
        value_type: str = None,
        **metric_kwargs
    ):
        super().__init__(handler, name=name, title=title, description=description)

        self.time_unit = time_unit
        self.value_unit = value_unit
        self.value_type = value_type
        self.target_param = None
        self.metric_kwargs = metric_kwargs

        if self.parameters:
            self.type = 'function'

    def handle_target_param(self):
        param = (self.parameters or {}).get(self.TARGET_PARAM)
        if param:
            if param.get('required'):
                target_param = 'required'
            else:
                target_param = 'optional'
            pop(self.parameters, self.TARGET_PARAM)
        else:
            target_param = None
        self.target_param = target_param

    def parametrize(self, name: str, kwargs: dict):
        return ParametrizedMetric(self, name=name, kwargs=kwargs)

    def dict(self) -> MetricData:
        return MetricData(
            type=self.type,
            time_unit=self.time_unit,
            value_unit=self.value_unit,
            value_type=self.value_type,
            target_param=self.target_param,
            **self.metric_kwargs,
            **super().dict(),
        )

    def __call__(self, registry, **kwargs):
        if self.type == 'function':
            return ParametrizedMetric(self, kwargs=kwargs)
        return self.handler(registry, **kwargs)


class ParametrizedMetric(BaseMetric):
    type = 'parametrized'

    def __init__(
        self,
        function: BaseMetric,
        kwargs: dict,
        name: str = None,
        title: str = None,
        description: str = '',
    ):
        if not kwargs:
            raise ValueError('ParametrizedMetric: kwargs cannot be empty')
        if function.type != 'function':
            raise ValueError('ParametrizedMetric: function metric type must be function')
        if not isinstance(kwargs, dict):
            raise ValueError('ParametrizedMetric: kwargs must be a dict')
        self.title = title
        self.description = description
        self.function = function
        self.kwargs = kwargs

        super().__init__(
            self.get_func(function.handler),
            name=name or f'{function.name}_(%s)' % f','.join(f'{k}={v}' for k, v in kwargs.items()),
            title=title or function.title,
            description=description or function.description,
            function=function.name,
            time_unit=function.time_unit,
            value_unit=function.value_unit,
            value_type=function.value_type,
            kwargs=normalize(kwargs, _json=True),
            **function.metric_kwargs
        )

    def get_func(self, f):
        return partial(f, **self.kwargs)


class ComputedMetric(BaseMetric):
    type = 'computed'

    class Component:
        def __init__(self, metric: Optional[BaseMetric], multiplier: float = 1, inverse: bool = False):
            self.metric = metric
            self.multiplier = multiplier
            self.inverse = inverse

        def sub(self):
            return self.__class__(
                metric=self.metric,
                multiplier=-self.multiplier,
                inverse=self.inverse
            )

        def div(self):
            return self.__class__(
                metric=self.metric,
                multiplier=self.multiplier,
                inverse=not self.inverse
            )

        def dict(self):
            return dict(
                name=self.metric.name if self.metric else None,
                ref=self.metric.ref if self.metric else None,
                multiplier=self.multiplier,
                inverse=self.inverse
            )

        @property
        def component_name(self):
            name = self.metric.name
            if self.multiplier != 1:
                name += f'_{self.multiplier}'
            if self.inverse:
                name += f'_inverse'
            return name

        def __call__(self, *args, **kwargs):
            if self.metric:
                value = self.metric(*args, **kwargs)
            else:
                value = 1
            if not isinstance(value, VALUE_TYPES):
                return 0
            if isinstance(value, Decimal):
                value = float(value)
            if self.multiplier != 1:
                value = value * self.multiplier
            if self.inverse and value:
                value = 1 / value
            return value

    def __init__(
        self,
        operator: Literal['sum', 'prod'],
        components: List[Component],
        name: str = None,
        title: str = None,
        description: str = '',
        value_unit: str = None,
        value_type: str = None,
    ):
        if not components:
            raise ValueError('ComputedMetric: components cannot be empty')
        if len({c.metric.time_unit for c in components}) > 1:
            raise ValueError(f'ComputedMetric: component metrics must have the same time_unit')
        for comp in components:
            if comp.metric.type in ['function', 'aggregated']:
                raise ValueError(f'ComputedMetric: component metrics type must be function or aggregated')

        self.operator = operator
        self.components = components
        self.title = title
        self.description = description
        super().__init__(
            self.func,
            name=name or f'{operator}_{"_".join([c.component_name for c in components])}',
            time_unit=components[0].metric.time_unit,
            value_type=value_type,
            value_unit=value_unit,
            title=title,
            description=description,
            operator=self.operator,
            components=[c.dict() for c in components]
        )

    def func(self, registry):
        values = []
        for comp in self.components:
            value = comp(registry)
            values.append(value)
        if self.operator == 'sum':
            return sum(values)
        elif self.operator == 'prod':
            res = 1
            for val in values:
                res *= val
            return res
        return 0


class AggregatedMetric(BaseMetric):
    type = 'aggregated'

    def __init__(
        self,
        aggregator: Literal['max', 'min', 'sum', 'p50', 'p95', 'p99', 'avg'],
        base: BaseMetric,
        time_unit: Literal['year', 'quarter', 'month', 'week', 'day'] = 'day',
        name: str = None,
        title: str = None,
        description: str = '',
    ):
        self.base = base
        self.aggregator = aggregator
        if not base.time_unit:
            raise ValueError('AggregatedMetric base metric should have time_unit')
        if TIME_UNITS.index(base.time_unit) >= TIME_UNITS.index(time_unit):
            raise ValueError(f'AggregatedMetric base metric time_unit: {repr(base.time_unit)} '
                             f'should small than {repr(time_unit)}')
        super().__init__(
            self.func,
            name=name or f'{aggregator}_{base.name}_{time_unit}',
            time_unit=time_unit,
            value_type=base.value_type,
            value_unit=base.value_unit,
            aggregation_type=aggregator,
            aggregation_base=base.name,
            title=title,
            description=description,
        )

    def func(self):
        raise RuntimeError('AggregatedMetric cannot be calculated at runtime')


Max = partial(AggregatedMetric, 'max')
Min = partial(AggregatedMetric, 'min')
Sum = partial(AggregatedMetric, 'sum')
Avg = partial(AggregatedMetric, 'avg')
P50 = partial(AggregatedMetric, 'p50')
P95 = partial(AggregatedMetric, 'p95')
P99 = partial(AggregatedMetric, 'p99')


def report_metric(
    time_unit: Literal['year', 'quarter', 'month', 'week', 'day', 'hour'] = 'hour',
    # year: 按年
    # quarter: 按季度
    # month: 按月 (周一 + report_utcoffset)
    # week: 按周 (周一 + report_utcoffset)
    # day: 按天 (report_utcoffset)
    # hour: 按小时
    # time_unit_interval: int = 1,
    # use None as return to escape the current report
    value_type: str = None,
    aggregation_type: str = None,
    unit: str = None,
    title: str = None,
    description: str = '',
    source=None,
):
    def wrapper(f) -> BaseMetric:
        return BaseMetric(
            f,
            title=title,
            description=description,
            value_type=value_type,
            aggregation_type=aggregation_type,
            time_unit=time_unit,
            value_unit=unit,
            source_table=get_ref(source) if source else None,
        )
    return wrapper


class BaseMetricRegistry:
    __metrics__: Dict[str, BaseMetric] = {}
    __ref__: str

    to_time: datetime

    def __init_subclass__(cls, **kwargs):
        cls.__ref__ = get_ref(cls)
        metrics = dict(cls.__metrics__)
        for key, val in cls.__dict__.items():
            if val is None:
                if key in metrics:
                    metrics.pop(key)
            # elif inspect.isfunction(val):
            #     metric_data = getattr(val, '__metric_data__', None)
            #     if metric_data and isinstance(metric_data, dict):
            #         val = BaseMetric(val, MetricData(metric_data))
            #         setattr(cls, key, val)
            if isinstance(val, BaseMetric):
                val.setup(cls, name=key, ref=f'{cls.__ref__}.{key}')
                # consider the aggregated / computed metrics with no native class function
                metrics[key] = val
        cls.__metrics__ = metrics

    def __init__(self, to_time: datetime = None):
        self.to_time = to_time or time_now()
