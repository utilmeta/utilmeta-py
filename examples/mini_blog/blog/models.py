from django.db import models


class User(models.Model):
    username = models.CharField(max_length=20, unique=True)


class Article(models.Model):
    author = models.ForeignKey(User, related_name="articles", on_delete=models.CASCADE)
    content = models.TextField()
