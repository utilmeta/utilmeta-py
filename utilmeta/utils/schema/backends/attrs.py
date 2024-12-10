from utype import register_transformer, TypeTransformer, register_encoder
from collections.abc import Mapping


@register_transformer(attr="__attrs_attrs__")
def transform_attrs(transformer: TypeTransformer, data, cls):
    if not transformer.no_explicit_cast and not isinstance(data, (dict, Mapping)):
        data = transformer.to_dict(data)
    names = [v.name for v in cls.__attrs_attrs__]
    data = {k: v for k, v in data.items() if k in names}
    return cls(**data)


@register_encoder(attr="__attrs_attrs__")
def encode_attrs(encoder, data):
    values = {}
    for v in data.__attrs_attrs__:
        if hasattr(data, v.name):
            values[v.name] = getattr(data, v.name)
    return values
