from __future__ import annotations
import pytest
from utilmeta.core import api, orm


class TestAPIClass:
    def test_declaration(self):
        class _API(api.API):    # noqa
            class QuerySchema(orm.Query):
                a: int
                b: str

            @api.get
            def test(self, query: QuerySchema):
                # QuerySchema will be string by default under from __future__ import annotations
                # we use API.__dict__ as local vars to evaluate the forward ref
                pass

        assert _API.test.wrapper.properties['query'].prop.__ident__ == 'query'
