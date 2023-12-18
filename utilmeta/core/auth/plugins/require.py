from utilmeta.utils import exceptions, awaitable
from utilmeta.core.request import var
from utilmeta.utils.plugin import Plugin
import inspect
from typing import Callable, TYPE_CHECKING
if TYPE_CHECKING:
    from utilmeta.core.api import API


class AuthValidatorPlugin(Plugin):
    # not_login_error = exceptions.Unauthorized('login required')
    # scope_insufficient_error = exceptions.PermissionDenied('insufficient scope')

    # ---------
    # these following attrs can be override
    user_var = var.user
    user_id_var = var.user_id
    scopes_var = var.scopes

    @staticmethod
    def login(user):
        if not user:
            raise exceptions.Unauthorized('login required')
        return True

    def __init__(self, *scope_or_fns, name: str = None):
        self.scopes = [s for s in scope_or_fns if isinstance(s, str)]
        self.functions = [f for f in scope_or_fns if callable(f)]
        super().__init__(scopes=self.scopes, functions=self.functions, name=name)
        if not scope_or_fns:
            self.functions = [self.login]
            name = name or 'login'
        self.name = name
        # self.login = login

    def enter_endpoint(self, api: 'API', *args, **kwargs):
        if self.functions:
            self.validate_functions(api)
        if self.scopes:
            self.validate_scopes(api)

    @awaitable(enter_endpoint)
    async def enter_endpoint(self, api: 'API', *args, **kwargs):
        if self.functions:
            await self.validate_functions(api)
        if self.scopes:
            await self.validate_scopes(api)

    def validate_scopes(self, api: 'API'):
        scopes = self.scopes_var.get(api.request)
        if not set(scopes or []).issuperset(self.scopes):
            raise exceptions.PermissionDenied(
                'insufficient scope',
                scopes=scopes,
                required_scopes=self.scopes,
                name=self.name
            )

    @awaitable
    async def validate_scopes(self, api: 'API'):
        scopes = await self.scopes_var.get(api.request)
        if not set(scopes or []).issuperset(self.scopes):
            raise exceptions.PermissionDenied(
                'insufficient scope',
                scopes=scopes,
                required_scopes=self.scopes,
                name=self.name
            )

    def validate_functions(self, api: 'API'):
        user = self.user_var.get(api.request)
        if user is None:
            pass
        for func in self.functions:
            func: Callable
            v = func(user)
            if not v:
                raise exceptions.PermissionDenied(
                    f'{self.name or "permission"} required',
                    name=self.name
                )

    @awaitable(validate_functions)
    async def validate_functions(self, api: 'API'):
        user = await self.user_var.get(api.request)
        if user is None:
            pass
        for func in self.functions:
            func: Callable
            v = func(user)
            if inspect.isawaitable(v):
                v = await v
            if not v:
                raise exceptions.PermissionDenied(
                    f'{self.name or "permission"} required',
                    name=self.name
                )
