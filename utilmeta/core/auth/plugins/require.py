from utilmeta.utils import exceptions, awaitable
from utilmeta.core.request import var, Request
from utilmeta.core.api.plugins.base import APIPlugin
import inspect
from typing import Callable


class AuthValidatorPlugin(APIPlugin):
    # not_login_error = exceptions.Unauthorized('login required')
    # scope_insufficient_error = exceptions.PermissionDenied('insufficient scope')

    # ---------
    # these following attrs can be override
    user_var = var.user
    user_id_var = var.user_id
    scopes_var = var.scopes
    __all = '*'

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
        # self.readonly = readonly
        # self.login = login

    def process_request(self, request: Request):
        if request.is_options:
            return
        if self.functions:
            self.validate_functions(request)
        if self.scopes:
            self.validate_scopes(request)

    @awaitable(process_request)
    async def process_request(self, request: Request):
        if request.is_options:
            return
        if self.functions:
            await self.async_validate_functions(request)
        if self.scopes:
            self.validate_scopes(request)

    def validate_scopes(self, request: Request):
        scopes = self.scopes_var.getter(request)
        if not scopes:
            scopes = []
        elif not isinstance(scopes, list):
            scopes = [scopes]
        if self.__all and self.__all in scopes:
            return
        if not set(scopes or []).issuperset(self.scopes):
            raise exceptions.PermissionDenied(
                'insufficient scope',
                scope=scopes,
                required_scope=self.scopes,
                name=self.name
            )

    def validate_functions(self, request: Request):
        user = self.user_var.getter(request)
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

    async def async_validate_functions(self, request: Request):
        user = await self.user_var.getter(request)
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
