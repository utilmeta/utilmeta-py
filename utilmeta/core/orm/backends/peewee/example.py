from peewee import *
from utilmeta.core import module

database = SqliteDatabase('my_db')

# model definitions -- the standard "pattern" is to define a base model class
# that specifies which database to use.  then, any subclasses will automatically
# use the correct storage.


class BaseModel(Model):
    class Meta:
        database = database

# the user model specifies its fields (or columns) declaratively, like django


class User(BaseModel):
    username = CharField(unique=True)
    password = CharField()
    email = CharField()
    join_date = DateTimeField()


a = User.username.contains


query = module.Query({
    'username_contains': User.username.contains(module.P),
    'data>': User.join_date > module.P,
    'data>=': User.join_date >= module.P,
    'data<': User.join_date < module.P,
    'email_isnull': User.email.is_null(module.P)
})
