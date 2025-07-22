from utype import Field
from utilmeta.utils import multi
from typing import List


class Scope(Field):
    # cascade
    # if like, the comments or article is cascaded
    # we can use @template: {"comments": {"id": "", "body": "", "comments": "@cascade"}}
    # include=id,name,items{sub_field1,sub_field2}

    # TEMPLATE_ALIASES = ['template', 'includes', 'scope', 'fields']
    # EXCLUDES_ALIASES = ['excludes', 'skip']

    DEFAULT_BRACKETS = ('[', '(', '{')
    BRACKET_PAIRS = {
        "(": ")",
        "[": "]",
        "{": "}"
    }

    def __init__(
        self,
        excluded: bool = False,
        max_depth: int = None,
        ignore_invalids: bool = True,
        allow_recursive: bool = True,
        nested_brackets: List[str] = DEFAULT_BRACKETS,
        required: bool = False,
        **kwargs
    ):
        super().__init__(**kwargs, required=required)
        self.max_depth = max_depth
        self.ignore_invalids = ignore_invalids
        self.allow_recursive = allow_recursive
        self.nested_brackets = [b for b in nested_brackets or [] if b in self.DEFAULT_BRACKETS]
        self.excluded = excluded

    def parse_scope_str(self, fields_str: str):
        brackets = self.nested_brackets
        if not brackets:
            return {}

        left_brackets = {b: self.BRACKET_PAIRS[b] for b in brackets}
        right_brackets = {self.BRACKET_PAIRS[b]: b for b in brackets}

        # Helper: recursive parser
        def _parse(s, i, closing=None):
            result = {}
            name = ''
            while i < len(s):
                c = s[i]
                # End of this nested context
                if closing and c == closing:
                    if name:
                        result[name] = None
                        name = ''
                    return result, i + 1
                # Nesting start
                if c in left_brackets:
                    # current name is the object key
                    key = name.strip()
                    name = ''
                    # parse inside
                    nested, j = _parse(s, i + 1, left_brackets[c])
                    result[key] = nested
                    i = j
                    continue
                # Separator
                if c == ',':
                    if name:
                        result[name.strip()] = None
                        name = ''
                    i += 1
                    continue
                # Unexpected closing bracket
                if c in right_brackets:
                    # same as closing
                    if name:
                        result[name.strip()] = None
                        name = ''
                    return result, i
                # Regular character
                name += c
                i += 1
            # End of string
            if name:
                result[name.strip()] = None
            return result, i

        parsed, _ = _parse(fields_str, 0)
        return parsed

    def parse_scope(self, value) -> dict:
        if isinstance(value, str):
            return self.parse_scope_str(value)
        elif isinstance(value, dict):
            return value
        elif multi(value):
            scope = {}
            for val in value:
                scope.update(self.parse_scope(val))
            return scope
        return {}

    @property
    def schema_annotations(self):
        return {"class": "scope", "excluded": self.excluded}

    @property
    def default_type(self):
        # string syntax with comma, in the wrong type might be misparsed
        return str
