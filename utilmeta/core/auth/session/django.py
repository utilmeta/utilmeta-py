from utype.types import *
from typing import Union, Callable
from utype.parser.field import ParserField
from utilmeta.core.response import Response
from utilmeta.core.request import var
from utilmeta.utils import http_time
import warnings
from .base import BaseSession
from django.contrib.sessions.backends.base import SessionBase


class DjangoSession(BaseSession):
    def __init__(self,
                 engine: Union[str, Callable] = None,
                 cache_alias: str = 'default',
                 file_path: str = None,
                 serializer: str = None,
                 **kwargs
                 ):
        super().__init__(engine, **kwargs)
        self.cache_alias = cache_alias
        self.file_path = file_path
        self.serializer = serializer

    def get_engine(self, field: ParserField):
        engine = type(None)
        for e in field.input_origins:
            if e is not None and not isinstance(None, e):
                engine = e
                break
        if isinstance(None, engine):
            engine = self.engine
        if not issubclass(engine, SessionBase):
            raise TypeError(f'Invalid django engine: {engine}')
        return engine

    def init(self, field: ParserField):
        from utilmeta.core.server.backends.django import DjangoSettings
        dj_settings = DjangoSettings.config()
        if dj_settings:
            dj_settings.register(self)
        else:
            warnings.warn('No DjangoSettings is used in service')
        super().init(field)

    def as_django(self):
        return {
            'SESSION_CACHE_ALIAS': self.cache_alias,
            'SESSION_SERIALIZER': self.serializer,
            'SESSION_ENGINE': self.engine,
            'SESSION_EXPIRE_AT_BROWSER_CLOSE': self.expire_at_browser_close,
            'SESSION_FILE_PATH': self.file_path,
            **self.cookie.as_django(prefix='SESSION')
        }

    def login(self, request, key: str, expiry_age: int = None, user_id_var=var.user_id):
        new_user_id = user_id_var.getter(request)
        if new_user_id is None:
            return
        session: SessionBase = self.getter(request)
        if not session:
            return
        user_id = session.get(key)
        if user_id is None:
            if self.cycle_key_at_login:
                session.cycle_key()
        else:
            if str(user_id) != str(new_user_id):
                session.flush()
        session[key] = new_user_id
        if expiry_age is not None:
            session.set_expiry(expiry_age)

    def is_empty(self, session: SessionBase):
        return session.is_empty()

    def save_session(self, response: Response, session: SessionBase):
        if session.accessed:
            response.patch_vary_headers("Cookie")
        if (session.modified or self.save_every_request) and not session.is_empty():
            if response.status != 500:
                if session.get_expire_at_browser_close():
                    max_age = None
                    expires = None
                else:
                    max_age = session.get_expiry_age() or 0
                    expires_time = datetime.now() + timedelta(seconds=max_age)
                    expires = http_time(expires_time)
                # Save the session data and refresh the client cookie.
                # Skip session save for 500 responses, refs #3881.
                session.save()
                self._set_cookie(
                    response,
                    session_key=session.session_key,
                    max_age=max_age,
                    expires=expires,
                )
