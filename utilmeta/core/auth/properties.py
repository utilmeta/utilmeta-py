from utilmeta.utils import exceptions as exc
from utilmeta.utils import awaitable
from utilmeta.core.request import var, Request
from utilmeta.utils.context import Property
from utype.types import *
from utype.parser.field import ParserField
from utype.utils.datastructures import unprovided
from .base import BaseAuthentication
import inspect


class User(Property):
    DEFAULT_CONTEXT_VAR = var.user
    DEFAULT_ID_CONTEXT_VAR = var.user_id
    DEFAULT_SCOPES_CONTEXT_VAR = var.scopes

    def get_user_id(self, request: Request):
        data: Mapping = self.authentication.getter(request) or {}
        return data.get(self.key)

    @awaitable(get_user_id)
    async def get_user_id(self, request: Request):
        r = self.authentication.getter(request)
        if inspect.isawaitable(r):
            r = await r
        data: Mapping = r or {}
        return data.get(self.key)

    def get_user(self, request: Request):
        user_id = self.get_user_id(request)
        if user_id is not None and self.user_model:
            inst = self.query_user(**{self.field: user_id})
            if inst is not None:
                # user.set(inst)
                if self.scopes_field:
                    self.scopes_context_var.set(request, getattr(inst, self.scopes_field, []))
                return inst
        return None

    @awaitable(get_user)
    async def get_user(self, request: Request):
        user_id = await self.get_user_id(request)
        if user_id is not None and self.user_model:
            inst = await self.query_user(**{self.field: user_id})
            if inst is not None:
                # user.set(inst)
                if self.scopes_field:
                    self.scopes_context_var.set(request, getattr(inst, self.scopes_field, []))
                return inst
        return None

    def getter(self, request: Request, field: ParserField = None):
        user_var = self.context_var.init(request)
        # even if we registered factory
        # we still need to cache here
        # because parse_context will directly call getter
        if user_var.contains():
            # already cached
            return user_var.get()
        user = self.get_user(request)
        user_var.set(user)
        if not user:
            if field and type(None) in field.input_origins:
                return None
            if self.required:
                raise exc.Unauthorized
            return unprovided
        return user

    @awaitable(getter)
    async def getter(self, request: Request, field: ParserField = None):
        user_var = self.context_var.init(request)
        if user_var.contains():
            # already cached
            # use await in async context
            return await user_var.get()
        user = await self.get_user(request)
        user_var.set(user)
        if not user:
            if field and type(None) in field.input_origins:
                return None
            if self.required:
                raise exc.Unauthorized
            return unprovided
        return user

    def init(self, field: ParserField):
        if not self.user_model:
            if field.type and not isinstance(None, field.type):
                from utilmeta.core.orm.backends.base import ModelAdaptor
                self.user_model = ModelAdaptor.dispatch(field.type)
                self.prepare_fields()
        return super().init(field)
        # from utilmeta.adapt.orm.base import ModelAdaptor
        # self.user_models = [ModelAdaptor.dispatch(model) for model in field.input_origins]
        # # can use Union[User1, User2] to specify multiple models
        # if not self.user_models:
        #     raise ValueError(f'User model not specified')
        # self.parser_field = field
        # TODO: validate fields existent in user model

    def __init__(self,
                 user_model=None, *,
                 authentication: BaseAuthentication,
                 key: str = '_user_id',
                 field: str = 'id',
                 scopes_field=None,
                 login_fields=None,
                 login_time_field=None,
                 login_ip_field=None,
                 password_field=None,
                 default=unprovided,
                 required: bool = None,
                 # context var
                 context_var=None,
                 id_context_var=None,
                 scopes_context_var=None,
                 ):

        super().__init__(default=default, required=required)
        if not isinstance(authentication, BaseAuthentication):
            raise TypeError(f'Invalid authentication, must be instance of BaseAuthentication subclasses')

        from utilmeta.core.orm import ModelAdaptor
        self.user_model: ModelAdaptor = ModelAdaptor.dispatch(user_model)

        self.authentication = authentication
        self.authentication.apply_user_model(self.user_model)

        self.key = key

        self.login_fields = login_fields
        self.login_time_field = login_time_field
        self.login_ip_field = login_ip_field
        self.password_field = password_field
        self.scopes_field = scopes_field

        self.field = field

        # -------
        self.context_var = context_var or self.DEFAULT_CONTEXT_VAR
        self.id_context_var = id_context_var or self.DEFAULT_ID_CONTEXT_VAR
        self.scopes_context_var = scopes_context_var or self.DEFAULT_SCOPES_CONTEXT_VAR

        if self.user_model:
            # register hook for request context var
            self.context_var.register_factory(self.get_user)
            self.id_context_var.register_factory(self.get_user_id)
            self.prepare_fields()

    @property
    def headers(self):
        return self.authentication.headers

    def prepare_fields(self):
        if self.login_fields:
            if isinstance(self.login_fields, (list, tuple, set)):
                self.login_fields = [self.validate_field(f) for f in self.login_fields]
            else:
                self.login_fields = [self.validate_field(self.login_fields)]
        else:
            self.login_fields = []
        self.login_time_field = self.validate_field(self.login_time_field)
        self.login_ip_field = self.validate_field(self.login_ip_field)
        self.password_field = self.validate_field(self.password_field)
        self.scopes_field = self.validate_field(self.scopes_field)

    def validate_field(self, f):
        if not f:
            return None
        if isinstance(f, str):
            field = self.user_model.get_field(f)
        else:
            # if not self.user_model.field_adaptor_cls.qualify(f):
            #     raise ValueError(f'Invalid field: {f}')
            field = self.user_model.field_adaptor_cls(f)
            # if not self.user_model.is_sub_model(field.model):
            #     warnings.warn('This field is not ')
        return field.name

    def query_user(self, q=None, **kwargs):
        if self.user_model:
            inst = self.user_model.get_instance(q, **kwargs)
            if inst is not None:
                return inst
        return None

    @awaitable(query_user)
    async def query_user(self, q=None, **kwargs):
        if self.user_model:
            inst = await self.user_model.get_instance(q, **kwargs)
            if inst is not None:
                return inst
        return None

    def query_login_user(self, token: str):
        if self.login_fields:
            if len(self.login_fields) == 1:
                return self.query_user(**{self.login_fields[0]: token})
            from utilmeta.core.orm.backends.django.expressions import Q
            q = Q()
            for f in self.login_fields:
                q |= Q(**{f: token})
            return self.query_user(q)
        else:
            return None

    @awaitable(query_login_user)
    async def query_login_user(self, token: str):
        if self.login_fields:
            if len(self.login_fields) == 1:
                return await self.query_user(**{self.login_fields[0]: token})
            from utilmeta.core.orm.backends.django.expressions import Q
            q = Q()
            for f in self.login_fields:
                q |= Q(**{f: token})
            return await self.query_user(q)
        else:
            return None

    def login(self, request: Request, token: str, password: str, expiry_age: int = None):
        user = self.query_login_user(token)
        if not user:
            return None
        encoded_password = getattr(user, self.password_field)
        if not self.check_password(password, encoded_password):
            return None
        self.login_user(request, user, expiry_age=expiry_age)
        return user

    @awaitable(login)
    async def login(self, request: Request, token: str, password: str, expiry_age: int = None):
        user = await self.query_login_user(token)
        if not user:
            return None
        encoded_password = getattr(user, self.password_field)
        if not self.check_password(password, encoded_password):
            return None
        await self.login_user(request, user, expiry_age=expiry_age)
        return user

    def login_user(self, request: Request, user, expiry_age: int = None, ignore_updates: bool = False):
        self.context_var.set(request, user)
        self.id_context_var.set(request, getattr(user, 'pk', None) or getattr(user, 'id', None))
        try:
            data = self.authentication.login(request, self.key, expiry_age)
        except NotImplementedError:
            data = None
        # cls.update_fields(request, user=user)
        # rotate_token(request.get_original_request())  # reset CSRF token for security purposes
        if not ignore_updates:
            self.update_fields(request, user, data)

    @awaitable(login_user)
    async def login_user(self, request: Request, user, expiry_age: int = None, ignore_updates: bool = False):
        self.context_var.set(request, user)
        self.id_context_var.set(request, getattr(user, 'pk', None) or getattr(user, 'id', None))
        try:
            data = self.authentication.login(request, self.key, expiry_age)
            if inspect.isawaitable(data):
                data = await data
        except NotImplementedError:
            data = None
        if not ignore_updates:
            await self.update_fields(request, user, data)

    def get_update_data(self, request: Request, data=None):
        data = data or {}
        if self.login_time_field:
            data.update({self.login_time_field: request.time})
        if self.login_ip_field:
            data.update({self.login_ip_field: str(request.ip_address)})
        if not data:
            return
        return data

    def update_fields(self, request: Request, user, data=None):
        data = self.get_update_data(request, data=data)
        if data:
            self.user_model.update(data, pk=user.pk)

    @awaitable(update_fields)
    async def update_fields(self, request: Request, user, data=None):
        data = self.get_update_data(request, data=data)
        if data:
            await self.user_model.update(data, pk=user.pk)

    @classmethod
    def check_password(cls, password: str, encoded: str):
        # you can override this method
        from django.contrib.auth.hashers import check_password
        return check_password(password, encoded)
