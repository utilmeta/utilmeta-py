from django.db import models
from utilmeta.core.orm.backends.django.models import PasswordField, AwaitableModel, AbstractSession


class User(AwaitableModel):
    # test abstract inherit with some field set None
    # objects = Manager()
    username = models.CharField(max_length=20, unique=True)
    # email = models.EmailField()
    password = PasswordField(min_length=6, max_length=20)
    jwt_token = models.TextField(default=None, null=True)
    avatar = models.FileField(upload_to="image/avatar", default=None, null=True)
    # admin = BooleanField(default=False)
    # signup_time = DateTimeField(auto_now_add=True)
    followers = models.ManyToManyField(
        "self",
        symmetrical=False,
        through="Follow",
        through_fields=("target", "user"),
        related_name="followings",
    )
    # email = None    # test set None; and it's following reaction on schema generator
    admin = models.BooleanField(default=False)
    signup_time = models.DateTimeField(auto_now_add=True)

    last_login_time = models.DateTimeField(auto_now=True)
    last_login_ip = models.GenericIPAddressField(default=None, null=True)
    last_activity = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user"


class Follow(AwaitableModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_followings")
    target = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_followers")
    follow_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "follow"
        unique_together = ("user", "target")


class BaseContent(AwaitableModel):
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    public = models.BooleanField(default=False)
    liked_bys = models.ManyToManyField(User, related_name="likes", db_table="liked")
    author = models.ForeignKey(User, related_name="contents", on_delete=models.CASCADE)
    author_id: int
    type = models.CharField(max_length=20, default="article")

    class Meta:
        db_table = "content"
        ordering = ["-created_at", "-updated_at"]


class Article(BaseContent):
    title = models.CharField(max_length=40)
    description = models.TextField(default="")
    slug = models.SlugField(db_index=True, unique=True)
    views = models.PositiveIntegerField(default=0)
    tags = models.JSONField(default=list)
    # in Windows under 3.9, JSON field cannot be processed by SQLite
    # if sys.version_info >= (3, 9):
    #     tags = models.JSONField(default=list)

    class Meta:
        db_table = "article"


class Comment(BaseContent):
    # can be recursive
    on_content = models.ForeignKey(BaseContent, related_name="comments", on_delete=models.CASCADE)
    on_content_id: int

    class Meta:
        db_table = "comment"


class Session(AbstractSession):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions', default=None, null=True)
    ip = models.GenericIPAddressField(default=None, null=True)
    # in Windows under 3.9, JSON field cannot be processed by SQLite
    # if sys.version_info >= (3, 9):
    # ua = models.JSONField(default=dict)

    class Meta:
        db_table = 'session'


class ArticleStats(AwaitableModel):
    article_id = models.PositiveIntegerField()
    comments_num = models.PositiveIntegerField(default=0)
    liked_bys_num = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "article_stats"
        managed = False
