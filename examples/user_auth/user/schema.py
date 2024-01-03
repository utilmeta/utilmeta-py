from utilmeta.core import orm
from .models import User
from datetime import datetime


class LoginSchema(orm.Schema[User]):
    username: str
    password: str = orm.Field(mode='wa')


class UserSchema(LoginSchema):
    id: int = orm.Field(no_input='wa')
    signup_time: datetime
