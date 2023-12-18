from .app.schema import UserBase
from utilmeta.core import orm


def create_user(user: UserBase[orm.A]):
    if user.avatar:
        pass
