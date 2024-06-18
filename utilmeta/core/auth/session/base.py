import inspect
from utilmeta.conf.http import Cookie
from typing import Union, Literal
import warnings
from utype.parser.field import ParserField
from utilmeta.core.request import Request, var
from utilmeta.core.response import Response
from utilmeta.utils.plugin import Plugin
from utilmeta.utils import import_obj, awaitable, localhost
from ..base import BaseAuthentication


class BaseSession(BaseAuthentication):
    __private__ = True
    name = 'session'
    Cookie = Cookie
    DEFAULT_CONTEXT_VAR = var.RequestContextVar('_session', cached=True)
    DEFAULT_ENGINE = None
    headers = [
        'cookie'
    ]

    def get_session(self, request: Request, engine=None):
        session_key = request.cookies.get(self.cookie_name)
        # if not session_key:
        #     return None
        # inst = self.engine(session_key)
        # req_session.set(inst)
        # guarantee there are only one session in a request
        return (engine or self.engine)(session_key)

    def getter(self, request: Request, field: ParserField = None):
        cvar = self.context_var.setup(request)
        if cvar.contains():
            return cvar.get()
        engine = None
        if field:
            # maybe a field has its own session schema as engine
            engine = self.get_engine(field)
        session = self.get_session(request, engine)
        cvar.set(session)
        return session

    def get_engine(self, field: ParserField):
        engine = type(None)
        for e in field.input_origins:
            if e is not None and not isinstance(None, e):
                engine = e
                break
        if isinstance(None, engine) or not engine:
            engine = self.engine
        if not callable(engine):
            raise TypeError('No engine specified')
        return engine

    def init(self, field: ParserField):
        if not self.engine:
            # try to assign engine if there is not one
            self.engine = self.get_engine(field)
        self.context_var.register_factory(self.get_session)
        return super().init(field)

    @property
    def plugin(_session_self) -> Plugin:
        class SessionPlugin(Plugin):
            def __init__(self, session=_session_self):
                super().__init__()
                self.session = session

            def process_response(self, response: Response, api=None):
                if not isinstance(response, Response):
                    response = Response(response, request=api.request if api else None)
                return self.session.process_response(response)

            @awaitable(process_response)
            async def process_response(self, response: Response, api=None):
                if not isinstance(response, Response):
                    response = Response(response, request=api.request if api else None)
                r = self.session.process_response(response)
                if inspect.isawaitable(r):
                    r = await r
                return r

        return SessionPlugin(_session_self)

    def __init__(self,
                 engine: Union[str, type] = None,
                 expire_at_browser_close: bool = False,
                 save_every_request: bool = False,
                 cycle_key_at_login: bool = True,
                 allow_localhost: bool = False,
                 interrupted: Literal['override', 'cycle', 'error'] = 'override',
                 cookie: Cookie = Cookie(http_only=True),
                 context_var=None,
                 ):
        super().__init__()
        assert isinstance(cookie, Cookie)
        if isinstance(engine, str):
            engine = import_obj(engine)
        self.engine = engine or self.DEFAULT_ENGINE
        # self.engine = import_obj(engine) if isinstance(engine, str) else engine
        self.cookie = cookie
        self.cookie_name = cookie.name or 'sessionid'
        if not self.cookie.http_only:
            warnings.warn(f'Session using cookie should turn http_only=True')

        self.context_var = context_var or self.DEFAULT_CONTEXT_VAR
        # self.cache_alias = cache_alias
        # self.file_path = file_path
        # self.options = options
        self.expire_at_browser_close = expire_at_browser_close
        self.save_every_request = save_every_request
        self.cycle_key_at_login = cycle_key_at_login
        self.interrupted = interrupted
        self.allow_localhost = allow_localhost

    def process_response(self, response: Response):
        """
        write based on django session middleware
        you can override
        """
        request = response.request
        cvar = self.context_var.setup(request)
        if not cvar.contains():
            # no session initialized
            return response
        if not isinstance(response, Response):
            response = Response(response)
        session = cvar.get()
        if session is None:
            # empty session still need to save
            return response
        # First check if we need to delete this cookie.
        # The session should be deleted only if the session is entirely empty.
        if self.cookie_name in request.cookies and self.is_empty(session):
            self.delete_cookie(response)
        else:
            self.save_session(response, session)
        return response

    @awaitable(process_response)
    async def process_response(self, response: Response):
        request = response.request
        cvar = self.context_var.setup(request)
        if not cvar.contains():
            # no session initialized
            return response
        if not isinstance(response, Response):
            response = Response(response)
        session = await cvar.get()
        if session is None:
            return response
        # First check if we need to delete this cookie.
        # The session should be deleted only if the session is entirely empty.
        if self.cookie_name in request.cookies and self.is_empty(session):
            self.delete_cookie(response)
        else:
            await self.save_session(response, session)
        return response

    def delete_cookie(self, response: Response):
        response.delete_cookie(
            self.cookie_name,
            path=self.cookie.path,
            domain=self.cookie.domain,
            # samesite=settings.SESSION_COOKIE_SAMESITE,
        )
        response.patch_vary_headers("Cookie")

    def is_empty(self, session):
        raise NotImplementedError

    def save_session(self, response: Response, session):
        raise NotImplementedError

    @awaitable(save_session)
    async def save_session(self, response: Response, session):
        raise NotImplementedError

    def _set_cookie(self, response: Response, session_key: str, max_age: int = None, expires: str = None):
        cookie_domain = self.cookie.domain
        secure = self.cookie.secure or None
        same_site = self.cookie.same_site
        if self.allow_localhost and response.request:
            if localhost(response.request.origin):
                secure = None
                cookie_domain = None
                if not localhost(response.request.host):
                    same_site = 'None'
                    secure = True
                    # secure is required to use SameSite=None
        response.set_cookie(
            self.cookie_name,
            session_key,
            max_age=max_age,
            expires=expires,
            domain=cookie_domain,
            path=self.cookie.path,
            secure=secure,
            httponly=self.cookie.http_only or None,
            samesite=same_site,
        )

    def openapi_scheme(self) -> dict:
        return {
            'type': 'apikey',
            'name': self.cookie_name,
            'in': 'cookie',
            'description': self.description or '',
        }
