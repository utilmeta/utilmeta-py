from tests.conftest import setup_service, db_using
#
setup_service(__name__, async_param=False)


def test_prepare_data(service, db_using):
    # from utilmeta.utils import exceptions as exc
    from django.db.utils import OperationalError, ProgrammingError
    # from server import service
    # setup service
    # service.setup()
    from app.models import User, Article, Comment, Follow, BaseContent
    from app.schema import UserSchema, ArticleSchema, CommentSchema
    # from domain.blog.models import Follow, BaseContent, SuperUser
    # from domain.blog.module import UserMain, ArticleMain, CommentMain, ArticleAdmin
    from utilmeta.core import orm

    try:
        User.objects.using(db_using).exists()
    except (OperationalError, ProgrammingError):
        from django.core.management import execute_from_command_line
        execute_from_command_line([__name__, 'migrate', f'--database={db_using}'])
        # os.system("python -m utilmeta migrate")

    # delete all data
    User.objects.all().using(db_using).delete()
    Article.objects.all().using(db_using).delete()
    Comment.objects.all().using(db_using).delete()
    Follow.objects.all().using(db_using).delete()

    # test bulk create
    UserSchema[orm.A].bulk_save(
        [
            dict(
                id=1,
                username="alice",
                password="alice123",
            ),
            dict(
                id=2,
                username="bob",
                password="bob123",
            ),
            dict(
                id=3,
                username="jack",
                password="jack123",
            ),
            dict(
                id=4,
                username="tony",
                password="tony123",
            ),
            dict(
                id=5,
                username="supervisor",
                admin=True,
                password="sudo-123",
            ),
        ],
        using=db_using
    )

    assert User.objects.using(db_using).count() == 5

    objs = [
        Follow(id=1, target_id=1, user_id=2),
        Follow(id=2, target_id=1, user_id=3),
        Follow(id=3, target_id=2, user_id=1),
        Follow(id=4, target_id=2, user_id=4),
        Follow(id=5, target_id=3, user_id=2),
    ]
    for obj in objs:
        obj.save(using=db_using)

    assert Follow.objects.using(db_using).count() == 5

    ArticleSchema[orm.A].bulk_save(
        [
            dict(
                id=1,
                author_id=2,
                title="big shot",
                # slug='big-shot',
                content="big shot content",
                views=10,
                tags=["shock", "head"],
            ),
            dict(
                id=2,
                author_id=2,
                title="Some News",
                content="news content",
                # slug='some-news',
                views=3,
            ),
            dict(
                id=3,
                author_id=2,
                title="this is a huge one",
                # slug='huge-one',
                content="huge one",
                views=0,
            ),
            dict(
                id=4,
                author_id=1,
                title="About tech",
                content="tech",
                # slug='about-tech',
                views=103,
            ),
            dict(
                id=5,
                author_id=4,
                # slug='nothing',
                title="nothing really matter",
                content="nothing",
                views=17,
                public=False
            ),
        ],
        using=db_using
    )

    CommentSchema[orm.A].bulk_save([
        dict(id=6, author_id=1, on_content_id=1, content="nice one"),
        dict(id=7, author_id=3, on_content_id=1, content="nice two"),
        dict(id=8, author_id=2, on_content_id=2, content="lol!"),
        dict(id=9, author_id=4, on_content_id=4, content="wow"),
        dict(id=10, author_id=5, on_content_id=4, content="brilliant~"),
    ], using=db_using)

    # reset sequences for PostgreSQL
    if db_using == 'postgresql':
        from django.db import connections
        for model in [User, BaseContent, Follow]:
            with connections[db_using].cursor() as cursor:
                table_name = model._meta.db_table
                max_id = model.objects.count()
                sql = f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), {max_id});"
                cursor.execute(sql)

    assert sorted([val.pk for val in Article.objects.all().using(db_using)]) == [1, 2, 3, 4, 5]
    assert sorted([val.pk for val in Comment.objects.all().using(db_using)]) == [6, 7, 8, 9, 10]
    assert BaseContent.objects.filter(public=True).using(db_using).count() == 9
    assert BaseContent.objects.filter(type="comment").using(db_using).count() == 5

    article_1 = Article.objects.using(db_using).get(id=1)
    article_2 = Article.objects.using(db_using).get(id=2)
    article_3 = Article.objects.using(db_using).get(id=3)
    article_4 = Article.objects.using(db_using).get(id=4)
    comment_6 = Comment.objects.using(db_using).get(id=6)
    comment_7 = Comment.objects.using(db_using).get(id=7)

    article_1.liked_bys.set([1, 3, 4])
    article_2.liked_bys.set([5])
    article_3.liked_bys.set([2, 5])
    article_4.liked_bys.set([1, 2])
    comment_6.liked_bys.set([1, 2, 4, 5])
    comment_7.liked_bys.set([2, 3])