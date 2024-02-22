from utilmeta.core import cli, request, api, response, file
import utype
from utype.types import *


class TestClient(cli.Client):
    @api.get("doc/{category}/{page}")
    def get_doc(self, category: str = request.PathParam('[a-zA-Z0-9-]{1,20}'),
                page: int = 1) -> response.Response:
        pass

    # query param is still the default?
    @api.get
    def query(self, page: int = request.QueryParam(),
              item: str = request.QueryParam("default")) -> response.Response: pass

    @api.get
    async def query(self, page: int = request.QueryParam(),
                    item: str = request.QueryParam("default")) -> response.Response: pass

    class QuerySchema(utype.Schema):
        page: int = utype.Field(ge=1, le=10)
        item: Optional[str] = utype.Field(min_length=3, max_length=10)

    @api.get
    def query_schema(self, query: QuerySchema = request.Query) -> QuerySchema: pass

    class MultiFormData(utype.Schema):
        name: str
        images: List[file.File]

    @api.post
    def multipart(self, data: MultiFormData = request.Body(content_type='multipart/form-data')): pass

    class DataSchema(utype.Schema):
        title: str = utype.Field(min_length=3, max_length=10)
        views: int = 0

    @api.post("log/{y}/{m}/{level}")
    def log(
        self,
        year: Optional[int] = utype.Field(ge=2000, alias='y'),
        month: Optional[int] = utype.Field(ge=1, le=12, alias='m'),
        level: Optional[str] = utype.Field(enum=["INFO", "WARN", "ERROR"]),
        status: int = utype.Field(ge=100, le=600, default=200),
        data: DataSchema = request.Body(
            max_length=30,
            content_type=request.Body.FORM_URLENCODED,
        ),
    ) -> Tuple[int, int, str, int, DataSchema]: pass
