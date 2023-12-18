from utype.types import *
from utilmeta.utils import exceptions as exc
from utype import Rule, Field


class ModelField(Field):
    def __init__(self, field: Union[str, Any] = 'id', *, rule: Rule = None,
                 not_found_error=exc.NotFound):
        self.field = get_field_name(field) or 'id'
        self.err_cls = not_found_error
        self.model = None
        self.field_rule = None
        self.extra_rule = rule
        self._getter = None
        self._setter = None
        self._rule = None

    def gen_converter(self):
        model = self.model
        if not model or not issubclass(model, Model):
            raise TypeError(f'Invalid model: {model}, must be subclass of Model')

        from utilmeta.utils import get_field_value

        def converter(value):
            if not self._setter:
                # cannot convert if setter is not specified
                return value

            query_value = self._getter(value) if callable(self._getter) else value if multi(value) else [value]
            if not query_value:
                # return the original value if query values is empty list
                return value

            qs = model.objects.filter(**{self.field + '__in': query_value})
            result_map = {}
            for obj in qs:
                field_value = get_field_value(obj, field=self.field)
                if field_value is not None:
                    result_map[str(field_value)] = obj

            if self.err_cls:
                not_exists_values = set([str(v) for v in query_value]).difference(result_map)
                if not_exists_values:
                    raise self.err_cls(f'{model.__name__} not found: '
                                       f'{self.field}__in={",".join(not_exists_values)}')

            return self._setter(value, result_map)

        return converter

    def resolve_model(self, annotate):
        """
        return getter, setter
        getter: get a serial values of model field value from the input value, always return list
        setter: set the value to the final output with the original input and the result map
        """
        import inspect
        from utilmeta.core.schema import SchemaMeta

        def default_setter(value, value_map: dict):  # str(field-value): Model-Instance
            return value_map.get(str(value))

        if isinstance(annotate, (SchemaMeta, dict)):
            raise TypeError(f'Request.Model not support schema template: {annotate}, '
                            f'please define it in inner level')

        if multi(annotate):
            if not annotate:
                return None, None, None

            getters = []
            setters = []
            rules = []
            for t in annotate:
                g, s, r = self.resolve_model(t)
                getters.append(g)  # including None, match the index
                setters.append(s)
                rules.append(r or t)

            if isinstance(annotate, tuple):
                def getter(value):
                    if not multi(value):
                        value = [value]
                    res = []
                    for val, _get in zip(value, getters):
                        if callable(_get):
                            res.extend(_get(val))
                    return res  # always return list for getter

                def setter(value, _map: dict):
                    if not multi(value):
                        value = [value]
                    res = []
                    for val, _set in zip(value, setters):
                        res.append(_set(val, _map) if callable(_set) else val)
                    return tuple(res)

                rule = Rule(template=tuple(rules))

            else:
                item_getter = getters[0]
                item_setter = setters[0]
                item_rule = rules[0]

                def getter(value):
                    if not callable(item_getter):
                        return []
                    if not multi(value):
                        value = [value]
                    res = []
                    for val in value:
                        res.extend(item_getter(val))
                    return res

                def setter(value, _map: dict):
                    if not multi(value):
                        value = [value]
                    res = []
                    for val in value:
                        res.append(item_setter(val, _map) if callable(item_setter) else val)
                    return type(annotate)(res)

                rule = Rule(template=[item_rule])
            return getter, setter, rule

        elif isinstance(annotate, Rule):
            if annotate.type_union:
                raise TypeError(f'Request.Model: not support Union type: {annotate.type_union}')

            dict_type = annotate.dict_type
            if dict_type:
                g0, s0, r0 = self.resolve_model(dict_type[0])
                g1, s1, r1 = self.resolve_model(dict_type[1])

                def getter(value):
                    if not isinstance(value, dict):
                        return []
                    values = []
                    for key, val in value.items():
                        if g0:
                            values.extend(g0(key))
                        if g1:
                            values.extend(g1(val))
                    return values

                def setter(value, _map: dict):
                    if not isinstance(value, dict):
                        return {}
                    res = {}
                    for key, val in value.items():
                        new_key = s0(key, _map) if callable(s0) else key
                        new_val = s1(val, _map) if callable(s1) else val
                        res[new_key] = new_val
                    return res

                return getter, setter, Rule(dict_type=(r0 or dict_type[0], r1 or dict_type[1]))
            elif annotate.template:
                return self.resolve_model(annotate.template)
            else:
                return self.resolve_model(annotate.type)
        elif inspect.isclass(annotate) and issubclass(annotate, Model):
            if self.model:
                if self.model != annotate:
                    raise ValueError(f'Request.Model: multiple model detected: {self.model}, {annotate}')
            else:
                from utilmeta.utils.field import QueryField
                self.model = annotate
                from utilmeta.utils import get_field

                def check_unique(f):
                    assert f.unique, f'Request.Model(model={self.model}) must specify an unique field, got {f}'

                # for lookup field like type__ident
                # require every field on the chain to be unique
                field = get_field(self.model, self.field, cascade=True, cascade_validator=check_unique)
                self.field_rule = Rule.make_required(QueryField.get_rule(field)) & self.extra_rule
            return lambda x: [x], default_setter, self.field_rule
        return None, None, None

    def generate_rule(self, annotate) -> Rule:
        # handle the following types
        # :Model         Model
        # :List[Model]  [Model]
        # :Optional[Model]  Rule(type=Model, null=True)
        # :Optional[List[User]]
        # :Union[Model, Any]    NOT SUPPORT
        # :Tuple[Model, int, str]
        # :Dict[Model, Any]
        # :Dict[Any, Model]
        # if no model is resolved, prompt a warning
        # if more than 1 model is resolved, raise an error
        # replace the Model class by field type
        from django.utils.functional import SimpleLazyObject
        self._getter, self._setter, self._rule = self.resolve_model(annotate)
        if not self.model:
            raise ValueError(f'Request.Model: no model class detected in type: {annotate}')

        def model_preprocessor(value):
            if isinstance(value, SimpleLazyObject):
                if issubclass(value.__class__, self.model):
                    return Rule.Breaker(value)
            if isinstance(value, self.model):
                return Rule.Breaker(value)  # break the following transform to remain the idempotent
            return value

        from utilmeta.utils import model_tag
        return Rule.gen_from(self._rule) & Rule(
            preprocessor=model_preprocessor,
            converter=self.gen_converter(),
            info=dict(model=model_tag(self.model))
        )
