from utilmeta import UtilMeta
from utilmeta.core import api
from config import configure
import django

service = UtilMeta(
    __name__,
    name='blog',
    backend=django,
    asynchronous=True,
    port=8080
)
configure(service)
# should import API after setup
from blog.api import ArticleAPI


@service.mount
@api.CORS(allow_origin='*')
class RootAPI(api.API):
    article: ArticleAPI


app = service.application()

if __name__ == '__main__':
    service.run()
