from utype import Field
from utilmeta.utils import multi
from typing import Union, List, Dict


class Scope(Field):
    # cascade
    # if like, the comments or article is cascaded
    # we can use @template: {"comments": {"id": "", "body": "", "comments": "@cascade"}}

    # TEMPLATE_ALIASES = ['template', 'includes', 'scope', 'fields']
    # EXCLUDES_ALIASES = ['excludes', 'skip']

    # todo: support related scope
    #  id,title,author(name,email)
    def __init__(
        self,
        excluded: bool = False,
        max_depth: int = None,
        ignore_invalids: bool = True,
        allow_recursive: bool = True,
        required: bool = False,
        **kwargs
    ):
        super().__init__(**kwargs, required=required)
        self.max_depth = max_depth
        self.ignore_invalids = ignore_invalids
        self.allow_recursive = allow_recursive
        self.excluded = excluded

    @classmethod
    def get_scope_value(cls, value):
        if isinstance(value, str):
            return {value: None}
        elif isinstance(value, dict):
            return value
        elif multi(value):
            return {v: None for v in value}
        return None

    @property
    def schema_annotations(self):
        return {"class": "scope", "excluded": self.excluded}

    @property
    def default_type(self):
        return Union[List[str], Dict[str, str]]
