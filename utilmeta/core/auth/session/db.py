import inspect

from .schema import BaseSessionSchema, SchemaSession, SessionCreateError
from typing import Type, TYPE_CHECKING
from utilmeta.utils import time_now
from datetime import timedelta
from utype import Field
from utilmeta.core.orm import ModelAdaptor

if TYPE_CHECKING:
    from utilmeta.core.orm.backends.django.models import AbstractSession


class DBSessionSchema(BaseSessionSchema):
    _config: "DBSession"
    # SESSION_ID_KEY: ClassVar = '$session_id'
    # CLIENT_IP_KEY: ClassVar = '$client_ip'
    # CLIENT_UA_KEY: ClassVar = '$client_ua'

    @property
    def _model_cls(self):
        return self._config.session_model

    def db_exists(self, session_key: str) -> bool:
        if not session_key:
            return False
        return self._model_cls.query().filter(session_key=session_key).exists()

    # @awaitable(exists)
    async def adb_exists(self, session_key: str) -> bool:
        if not session_key:
            return False
        return await self._model_cls.query().filter(session_key=session_key).aexists()

    def exists(self, session_key: str) -> bool:
        return self.db_exists(session_key)

    # @awaitable(exists)
    async def aexists(self, session_key: str) -> bool:
        return await self.adb_exists(session_key)

    def create(self):
        self._session_key = self._get_new_session_key()
        try:
            self.save(must_create=True)
        except SessionCreateError:
            return
        self._modified = True
        return

    # @awaitable(create)
    async def acreate(self):
        self._session_key = await self._aget_new_session_key()
        try:
            await self.asave(must_create=True)
        except SessionCreateError:
            return
        self._modified = True
        return

    @property
    @Field(no_output=True)
    def timeout(self) -> int:
        # if expiry_age=0 (at browser close), still means a not clear timeout
        return self.expiry_age or self._config.cookie.age

    def get_session_data(self):
        return dict(
            session_key=self.session_key,
            encoded_data=self.encode(dict(self)),
            expiry_time=time_now() + timedelta(seconds=self.timeout),
            last_activity=time_now(),
            created_time=self._request.time if self._request else time_now(),
        )

    def load_object(self, must_create: bool = False):
        session_id = None
        if not self.session_key:
            self._session_key = self._get_new_session_key()
        elif not must_create:
            obj = self._model_cls.filter(session_key=self.session_key).get_instance()
            session_id = obj.pk if obj else None
        return self._model_cls.init_instance(id=session_id, **self.get_session_data())

    async def aload_object(self, must_create: bool = False):
        session_id = None
        if not self.session_key:
            self._session_key = await self._aget_new_session_key()
        elif not must_create:
            obj = await self._model_cls.filter(
                session_key=self.session_key
            ).aget_instance()
            session_id = obj.pk if obj else None
        data = self.get_session_data()
        if inspect.isawaitable(data):
            data = await data
        return self._model_cls.init_instance(id=session_id, **data)

    def db_save(self, must_create=False):
        if self.session_key is None:
            return self.create()
        # obj = self.load_object(must_create)
        # if not obj.pk:
        #     must_create = True
        # if not must_create and obj.pk:
        #     self._model_cls.query(pk=obj.pk).update(self.get_session_data())
        # else:
        #     obj.save(force_insert=must_create, force_update=not must_create and force)
        if must_create:
            try:
                self._model_cls.query().create(self.get_session_data())
            except Exception as e:
                raise SessionCreateError(f'Create session failed with error: {e}') from e
            return
        # update or create
        self._model_cls.query().update_or_create(
            session_key=self.session_key,
            defaults=self.get_session_data(),
        )

    # @awaitable(db_save)
    async def adb_save(self, must_create=False):
        if self.session_key is None:
            return await self.acreate()
        # obj = await self.aload_object(must_create)
        # if not obj.pk:
        #     must_create = True
        # await obj.asave(
        #     force_insert=must_create, force_update=not must_create and force
        # )
        if must_create:
            try:
                await self._model_cls.query().acreate(self.get_session_data())
            except Exception as e:
                raise SessionCreateError(f'Create session failed with error: {e}') from e
            return
        # update or create
        await self._model_cls.query().aupdate_or_create(
            session_key=self.session_key,
            defaults=self.get_session_data(),
        )

    def save(self, must_create: bool = False):
        return self.db_save(must_create)

    # @awaitable(save)
    async def asave(self, must_create: bool = False):
        return await self.adb_save(must_create)

    def db_delete(self, session_key=None):
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key
        self._model_cls.query().filter(
            session_key=session_key, deleted_time=None
        ).update(deleted_time=time_now())

    # @awaitable(db_delete)
    async def adb_delete(self, session_key=None):
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key
        await self._model_cls.query().filter(
            session_key=session_key, deleted_time=None
        ).aupdate(deleted_time=time_now())

    def delete(self, session_key: str = None):
        return self.db_delete(session_key)

    # @awaitable(delete)
    async def adelete(self, session_key: str = None):
        return await self.adb_delete(session_key)

    def load(self):
        if not self._session_key:
            return None
        # to be inherited
        session = self._model_cls.filter(
            session_key=self._session_key,
            deleted_time=None,
        ).get_instance()
        if session:
            return self.decode(session.encoded_data)
        return None

    async def aload(self):
        if not self._session_key:
            return None
        # to be inherited
        session = await self._model_cls.filter(
            session_key=self._session_key, deleted_time=None
        ).aget_instance()
        if session:
            return self.decode(session.encoded_data)
        return None


class DBSession(SchemaSession):
    DEFAULT_ENGINE = DBSessionSchema
    schema = DBSessionSchema

    def __init__(self, session_model: Type["AbstractSession"], **kwargs):
        super().__init__(**kwargs)
        self.session_model: ModelAdaptor = ModelAdaptor.dispatch(session_model)
