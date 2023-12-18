# API 路由


## 路由规则



## API 公共参数

如果一个 API 中的所有接口都需要携带某一参数，那么可以将这个参数作为该 API 的公共参数进行声明，声明的方式很简单，就是将它定义为 API 类中的一个变量

```python
@api.route('{slug}/comments')
class CommentAPI(API):
    slug: str = request.SlugPathParam

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.article: Optional[Article] = None

    @api.get
    async def get(self):
        return await CommentSchema.aserialize(
			Comment.objects.filter(article=self.article)
		)

    @api.before('*')
    async def handle_article(self):
        article = await Article.objects.filter(slug=self.slug).afirst()
        if not article:
            raise exceptions.NotFound('article not found')
        self.article = article
```


::: tip
公共参数需要指定一个 request 中的参数类型
:::


## 钩子机制


## 响应模板

