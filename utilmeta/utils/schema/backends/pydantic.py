from utype import register_transformer, TypeTransformer
from collections.abc import Mapping
from pydantic import BaseModel


@register_transformer(BaseModel)
def transform_attrs(transformer: TypeTransformer, data, cls):
    if not transformer.no_explicit_cast and not isinstance(data, Mapping):
        data = transformer(data, dict)
    return cls(**data)
