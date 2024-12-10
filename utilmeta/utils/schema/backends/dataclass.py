from utype import register_transformer, TypeTransformer, register_encoder
from collections.abc import Mapping


@register_transformer(attr="__dataclass_fields__")
def transform_attrs(transformer: TypeTransformer, data, cls):
    if not transformer.no_explicit_cast and not isinstance(data, (dict, Mapping)):
        data = transformer(data, dict)
    data = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
    return cls(**data)


@register_encoder(attr="__dataclass_fields__")
def transform_attrs(encoder, data):
    values = {}
    for k in data.__dataclass_fields__:
        if hasattr(data, k):
            values[k] = getattr(data, k)
    return values
