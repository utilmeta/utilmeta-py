from utilmeta.core import api
from user.api import UserAPI


@api.CORS(allow_origin='*')
class RootAPI(api.API):
    user: UserAPI
