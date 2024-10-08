from utilmeta.core import orm
import pytest
from tests.conftest import setup_service
#
setup_service(__name__, async_param=False)

from utype.types import *


class TestInvalidSchemas:
    def test_incorrect_related_model(self):
        from app.models import User
        from app.schema import ContentSchema

        with pytest.raises(Exception):
            class UserSchema(orm.Schema[User]):
                followers: List[ContentSchema]

    def test_non_exists_fields(self):
        from app.models import User

        with pytest.raises(Exception):
            class UserSchema(orm.Schema[User]):
                not_exists_field: str = orm.Field('not_exists_field')
