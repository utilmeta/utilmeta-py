from django.db import models
from utilmeta.core.orm.backends.django.models import AbstractSession, PasswordField


class User(models.Model):
    username = models.CharField(max_length=20, unique=True)
    password = PasswordField(max_length=100)
    signup_time = models.DateTimeField(auto_now_add=True)


class Session(AbstractSession):
    user = models.ForeignKey(User, related_name='sessions', null=True, default=None, on_delete=models.CASCADE)
