from utilmeta.core import cli, request, api, response, file
import utype
from utype.types import *


class DataSchema(utype.Schema):
    key: str


class DataResponse(response.Response):
    result_key = 'test'
    result: DataSchema


class UserSchema(utype.Schema):
    id: int
    username: str
    jwt_token: Optional[str]
    avatar: str
    followers_num: int
    signup_time: datetime


class UserResponse(response.Response):
    result: UserSchema


class UserClient(cli.Client):
    @api.post('user/jwt_login')
    def jwt_login(self, username: str = request.BodyParam(),
                  password: str = request.BodyParam()) -> Union[UserResponse, response.Response]:
        pass

    @api.get('user/user_by_jwt')
    def jwt_get(self, token: str = request.HeaderParam('authorization')) -> Union[UserResponse, response.Response]:
        pass

    @api.post('user/session_login')
    def session_login(self, username: str = request.BodyParam(),
                      password: str = request.BodyParam()) -> Union[UserResponse, response.Response]:
        pass

    @api.get('user/user_by_session')
    def session_get(self) -> Union[UserResponse, response.Response]:
        pass

    @api.post('user/session_logout')
    def session_logout(self):
        pass

    @api.patch('user')
    def update_user(self,
                    username: str = request.BodyParam(required=False),
                    password: str = request.BodyParam(required=False),
                    avatar: str = request.BodyParam(required=False),
                    ) -> Union[UserResponse, response.Response]:
        pass


class TestClient(cli.Client):
    @api.get("doc/{category}/{page}")
    def get_doc(self, category: str = request.PathParam('[a-zA-Z0-9-]{1,20}'),
                page: int = 1) -> response.Response:
        pass

    # query param is still the default?
    @api.get
    def query(self, page: int = request.QueryParam(),
              item: str = request.QueryParam()) -> response.Response: pass

    @api.get('query')
    async def async_query(self, page: int = request.QueryParam(),
                          item: str = request.QueryParam()) -> response.Response: pass

    @api.get("asynchronous")
    def get_asynchronous(self) -> response.Response: pass

    class QuerySchema(utype.Schema):
        page: int = utype.Field(ge=1, le=10)
        item: Optional[str] = utype.Field(min_length=3, max_length=10)

    @api.get
    def query_schema(self, query: QuerySchema = request.Query) -> response.Response[QuerySchema]: pass

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

    @api.get('@parent/data')
    def get_data(self, key: str) -> Union[DataResponse, response.Response]: pass
