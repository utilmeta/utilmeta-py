from utype import Field, types


class Page(Field):
    type = types.PositiveInt
    # parser_field_cls = ParserPagination

    def __init__(self, ge: int = 1, required: bool = False, **kwargs):
        super().__init__(**kwargs, required=required, ge=ge)

    @property
    def schema_annotations(self):
        return {'class': 'page'}


class Offset(Field):
    type = types.PositiveInt
    # parser_field_cls = ParserPagination

    def __init__(self, ge: int = 0, required: bool = False, **kwargs):
        super().__init__(**kwargs, required=required, ge=ge)

    @property
    def schema_annotations(self):
        return {'class': 'offset'}


class Limit(Field):
    type = types.PositiveInt
    # parser_field_cls = ParserPagination

    def __init__(self, ge: int = 0, required: bool = False, **kwargs):
        super().__init__(**kwargs, required=required, ge=ge)

    @property
    def schema_annotations(self):
        return {'class': 'limit'}
