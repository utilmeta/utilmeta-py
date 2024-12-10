from utype.utils.encode import JSONSerializer
from utype.utils.datastructures import unprovided
from utype import Schema, Field, Options
from utilmeta.utils import awaitable, gen_key, time_now, http_time, exceptions
from datetime import timedelta, datetime, timezone
from typing import Optional, TypeVar, Type, ClassVar, TYPE_CHECKING
import warnings
from .base import BaseSession
from utilmeta.core.request import var, Request
from utilmeta.core.response import Response
from utilmeta.conf import Preference

if TYPE_CHECKING:
    from utilmeta.core.request import Request

T = TypeVar("T")
EPOCH = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


class SessionError(Exception):
    pass


class SessionCreateError(SessionError):
    """
    Used internally as a consistent exception type to catch from save (see the
    docstring for SessionBase.save() for details).
    """

    pass


class SessionUpdateError(SessionError):
    """
    Occurs if Django tries to update a session that was deleted.
    """

    pass


class BaseSessionSchema(Schema):
    """
    Features:
    1. support both sync and async session
    2. use schema to define session fields
    """

    __options__ = Options(addition=True, ignore_required=True)

    _serializer_cls: ClassVar = JSONSerializer
    _config: "SchemaSession"
    _session_key = None
    _request: "Request" = None
    _modified = False

    # inner fields
    expiry: Optional[datetime] = Field(
        required=False, default=None, defer_default=True, alias="_session_expiry"
    )
    key_salt: ClassVar[str] = "utilmeta.core.auth.session.schema"
    # not based __class__, because it may change for different APIs

    @classmethod
    def init_from(cls: Type[T], session_key: str, config: "SchemaSession") -> T:
        self = cls.__new__(cls)
        if not isinstance(config, SchemaSession):
            raise TypeError(f"Invalid session config: {config}")
        self._config = config
        if session_key:
            if not isinstance(session_key, str):
                session_key = str(session_key)
            self._session_key = session_key
            data = self.load()
            if not isinstance(data, dict):
                data = {}
        else:
            data = {}
        cls.__init__(self, **data)
        return self

    @classmethod
    async def ainit_from(cls: Type[T], session_key: str, config: "SchemaSession") -> T:
        self = cls.__new__(cls)
        if not isinstance(config, SchemaSession):
            raise TypeError(f"Invalid session config: {config}")
        self._config = config
        if session_key:
            if not isinstance(session_key, str):
                session_key = str(session_key)
            self._session_key = session_key
            data = await self.aload()
            if not isinstance(data, dict):
                data = {}
        else:
            data = {}
        cls.__init__(self, **data)
        return self

    @classmethod
    def init(cls: Type[T], request: Request, config: "SchemaSession") -> T:
        # for developer to directly call
        if not isinstance(config, SchemaSession):
            raise TypeError(f"Invalid session config: {config}")
        cvar = config.context_var.setup(request)
        if cvar.contains():
            data: BaseSessionSchema = cvar.get()
            if not isinstance(data, cls):
                self = cls(**data)
                self._session_key = data.session_key
                self._config = config
                self._request = request
                self._modified = data.modified
                data = self
                cvar.set(data)
            return data
        session_key = request.cookies.get(config.cookie_name)
        # session key is not provided for every new user, but we need an empty session to create
        # if not session_key:
        #     raise ValueError(f'Session key not provided')
        session = cls.init_from(session_key, config)
        session._request = request
        cvar.set(session)
        return session

    @classmethod
    async def ainit(cls: Type[T], request: Request, config: "SchemaSession") -> T:
        if not isinstance(config, SchemaSession):
            raise TypeError(f"Invalid session config: {config}")
        cvar = config.context_var.setup(request)
        if cvar.contains():
            data: BaseSessionSchema = await cvar.get()
            if not isinstance(data, cls):
                self = cls(**data)
                self._session_key = data.session_key
                self._config = config
                self._request = request
                self._modified = data.modified
                data = self
                cvar.set(data)
            return data
        session_key = request.cookies.get(config.cookie_name)
        # if not session_key:
        #     raise ValueError(f'Session key not provided')
        session = await cls.ainit_from(session_key, config)
        session._request = request
        cvar.set(session)
        return session

    def __setitem__(self, alias: str, value):
        super().__setitem__(alias, value)
        self._modified = True

    def __field_setter__(self, value, field, setter=None):
        super().__field_setter__(value, field, setter)
        self._modified = True

    def __field_deleter__(self, field, deleter=None):
        super().__field_deleter__(field, deleter)
        self._modified = True

    @property
    @Field(no_output=True)
    def session_key(self):
        return self._session_key

    @property
    @Field(no_output=True)
    def loaded(self):
        return bool(self._session_key)

    @property
    @Field(no_output=True)
    def modified(self):
        return self._modified

    @property
    @Field(no_output=True)
    def is_empty(self):
        return not self.loaded and not self

    @property
    @Field(no_output=True)
    def request(self):
        return self._request

    # @property
    # @Field(no_output=True)
    # def key_salt(self):
    #     # not based __class__, because it may change for different APIs
    #     return BaseSessionSchema.__module__

    def pop(self, key, default=unprovided):
        self._modified = self.modified or key in self
        args = () if unprovided(default) else (default,)
        return super().pop(key, *args)

    def setdefault(self, key, default):  # noqa
        if key in self:
            return self[key]
        else:
            self._modified = True
            self[key] = default
            return default

    def encode(self, session_dict):
        from django.core import signing

        return signing.dumps(
            session_dict,
            salt=self.key_salt,
            serializer=self._serializer_cls,
            compress=True,
        )

    def decode(self, session_data):
        from django.core import signing

        try:
            return signing.loads(
                session_data, salt=self.key_salt, serializer=self._serializer_cls
            )
        except Exception as e:
            # ValueError, unpickling exceptions. If any of these happen, just
            # return an empty dictionary (an empty session).
            warnings.warn(f"Session data corrupted: {str(e)}")
        return {}

    def update(self, __m=None, **kwargs):
        super().update(__m, **kwargs)
        self._modified = True

    def clear(self):
        super().clear()
        self._modified = True

    def _get_new_session_key(self) -> str:
        pref = Preference.get()
        i = 0
        while True:
            session_key = gen_key(32, alnum=True, lower=True)
            if not self.exists(session_key):
                return session_key
            i += 1
            if i >= pref.max_retry_loops:
                raise exceptions.MaxRetriesExceed(max_retries=pref.max_retry_loops)

    # @awaitable(_get_new_session_key)
    async def _aget_new_session_key(self):
        pref = Preference.get()
        i = 0
        while True:
            session_key = gen_key(32, alnum=True, lower=True)
            if not await self.aexists(session_key):
                return session_key
            i += 1
            if i >= pref.max_retry_loops:
                raise exceptions.MaxRetriesExceed(max_retries=pref.max_retry_loops)

    def flush(self) -> None:
        """
        Remove the current session data from the database and regenerate the
        key.
        """
        self.clear()
        self.delete()
        self._session_key = None

    # @awaitable(flush)
    async def aflush(self) -> None:
        """
        Remove the current session data from the database and regenerate the
        key.
        """
        self.clear()
        await self.adelete()
        self._session_key = None

    def cycle_key(self) -> None:
        key = self._session_key
        self.create()
        if key:
            self.delete(key)

    # @awaitable(cycle_key)
    async def acycle_key(self) -> None:
        key = self._session_key
        await self.acreate()
        if key:
            await self.adelete(key)

    @property
    @Field(no_output=True)
    def expiry_age(self) -> int:
        """Get the number of seconds until the session expires.

        Optionally, this function accepts `modification` and `expiry` keyword
        arguments specifying the modification and expiry of the session.
        """
        expiry = self.expiry
        if not expiry:  # Checks both None and 0 cases
            return self._config.cookie.age
        return max(0, int((expiry - time_now(expiry)).total_seconds()))

    # Methods that child classes must implement.

    def exists(self, session_key):
        """
        Return True if the given session_key already exists.
        """
        raise NotImplementedError(
            "subclasses of SessionBase must provide an exists() method"
        )

    # @awaitable(exists)
    async def aexists(self, session_key):
        """
        Return True if the given session_key already exists.
        """
        raise NotImplementedError(
            "subclasses of SessionBase must provide an aexists() method"
        )

    def create(self):
        """
        Create a new session instance. Guaranteed to create a new object with
        a unique key and will have saved the result once (with empty data)
        before the method returns.
        """
        raise NotImplementedError(
            "subclasses of SessionBase must provide a create() method"
        )

    def acreate(self):
        """
        Create a new session instance. Guaranteed to create a new object with
        a unique key and will have saved the result once (with empty data)
        before the method returns.
        """
        raise NotImplementedError(
            "subclasses of SessionBase must provide a acreate() method"
        )

    def save(self, must_create=False):
        """
        Save the session data. If 'must_create' is True, create a new session
        object (or raise CreateError). Otherwise, only update an existing
        object and don't create one (raise UpdateError if needed).
        """
        raise NotImplementedError(
            "subclasses of SessionBase must provide a save() method"
        )

    # @awaitable(save)
    async def asave(self, must_create=False):
        raise NotImplementedError(
            "subclasses of SessionBase must provide a asave() method"
        )

    def delete(self, session_key=None):
        """
        Delete the session data under this key. If the key is None, use the
        current session key value.
        """
        raise NotImplementedError(
            "subclasses of SessionBase must provide a delete() method"
        )

    # @awaitable(delete)
    async def adelete(self, session_key=None):
        raise NotImplementedError(
            "subclasses of SessionBase must provide a adelete() method"
        )

    def load(self):
        """
        Load the session data and return a dictionary.
        """
        raise NotImplementedError(
            "subclasses of SessionBase must provide a load() method"
        )

    # @awaitable(load)
    async def aload(self):
        raise NotImplementedError(
            "subclasses of SessionBase must provide a aload() method"
        )


class SchemaSession(BaseSession):
    DEFAULT_ENGINE = BaseSessionSchema
    schema = BaseSessionSchema
    engine: Type[BaseSessionSchema]

    def __init__(self, engine=None, **kwargs):
        super().__init__(engine=engine, **kwargs)

        @self
        class schema(self.engine or self.DEFAULT_ENGINE):
            pass

        schema._config = self
        self.schema = schema

    def get_engine(self, field):
        engine = type(None)
        for e in field.input_origins:
            if e is not None and not isinstance(None, e):
                engine = e
                break
        if isinstance(None, engine):
            engine = self.engine
        if not issubclass(engine, self.DEFAULT_ENGINE):
            raise TypeError(f"Invalid SchemaSession engine: {engine}")
        return engine

    def get_session(self, request: Request, engine=None):
        session_key = request.cookies.get(self.cookie_name)
        # if not session_key:
        #     return None
        session = (engine or self.engine).init_from(session_key, config=self)
        session._request = request
        return session

    @awaitable(get_session)
    async def get_session(self, request: Request, engine=None):
        session_key = request.cookies.get(self.cookie_name)
        # if not session_key:
        #     return None
        session = await (engine or self.engine).ainit_from(session_key, config=self)
        session._request = request
        return session

    def getter(self, request: Request, field=None):
        cvar = self.context_var.setup(request)
        engine = None
        if field:
            # maybe a field has its own session schema as engine
            engine = self.get_engine(field)
        if cvar.contains():
            session: BaseSessionSchema = cvar.get()
            engine = engine or self.engine
            if not isinstance(session, engine):
                _session = self.engine(**session)
                _session._config = self
                _session._request = request
                _session._session_key = session.session_key
                _session._modified = session.modified
                session = _session
                cvar.set(session)
            return session
        session = self.get_session(request, engine)
        cvar.set(session)
        return session

    @awaitable(getter)
    async def getter(self, request: Request, field=None):
        cvar = self.context_var.setup(request)
        engine = None
        if field:
            # maybe a field has its own session schema as engine
            engine = self.get_engine(field)
        if cvar.contains():
            session: BaseSessionSchema = await cvar.get()
            engine = engine or self.engine
            if not isinstance(session, engine):
                _session = self.engine(**session)
                _session._config = self
                _session._request = request
                _session._session_key = session.session_key
                _session._modified = session.modified
                session = _session
                cvar.set(session)
            return session
        session = await self.get_session(request, engine)
        cvar.set(session)
        return session

    def login(self, request, key: str, expiry_age: int = None, user_id_var=var.user_id):
        new_user_id = user_id_var.getter(request)
        if new_user_id is None:
            return
        session: BaseSessionSchema = self.getter(request)
        if session is None:
            # NOT [not session]
            # because an empty dict is False in bool too
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
            if not expiry_age:
                session.expiry = EPOCH
            else:
                session.expiry = time_now() + timedelta(seconds=expiry_age)

    @awaitable(login)
    async def login(
        self, request, key: str, expiry_age: int = None, user_id_var=var.user_id
    ):
        new_user_id = await user_id_var.getter(request)
        if new_user_id is None:
            return
        session: BaseSessionSchema = await self.getter(request)
        if session is None:
            # NOT [not session]
            # because an empty dict is False in bool too
            return
        user_id = session.get(key)
        if user_id is None:
            if self.cycle_key_at_login:
                await session.acycle_key()
        else:
            if str(user_id) != str(new_user_id):
                await session.aflush()
        session[key] = new_user_id
        if expiry_age is not None:
            if not expiry_age:
                session.expiry = EPOCH
            else:
                session.expiry = time_now() + timedelta(seconds=expiry_age)

    def is_empty(self, session: BaseSessionSchema):
        return session.is_empty

    def save_session(self, response: Response, session: BaseSessionSchema):
        response.patch_vary_headers("Cookie")
        if (session.modified or self.save_every_request) and not session.is_empty:
            if response.status != 500:
                expiry = session.expiry
                expire_at_browser_close = (
                    self.expire_at_browser_close
                    if expiry is None
                    else expiry.timestamp() == 0
                )
                if expire_at_browser_close:
                    max_age = None
                    expires = None
                else:
                    max_age = session.expiry_age
                    expires = http_time(expiry)
                # Save the session data and refresh the client cookie.
                # Skip session save for 500 responses, refs #3881.
                session.save()
                self._set_cookie(
                    response,
                    session_key=session.session_key,
                    max_age=max_age,
                    expires=expires,
                )

    @awaitable(save_session)
    async def save_session(self, response: Response, session: BaseSessionSchema):
        response.patch_vary_headers("Cookie")
        if (session.modified or self.save_every_request) and not session.is_empty:
            if response.status != 500:
                expiry = session.expiry
                expire_at_browser_close = (
                    self.expire_at_browser_close
                    if expiry is None
                    else str(expiry).startswith("1970-01-01 00:00:00")
                )
                if expire_at_browser_close:
                    max_age = None
                    expires = None
                else:
                    max_age = session.expiry_age
                    expires = http_time(expiry)
                # Save the session data and refresh the client cookie.
                # Skip session save for 500 responses, refs #3881.
                await session.asave()
                self._set_cookie(
                    response,
                    session_key=session.session_key,
                    max_age=max_age,
                    expires=expires,
                )
