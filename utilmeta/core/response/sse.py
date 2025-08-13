from .base import Response
import inspect
from typing import TypeVar, AsyncIterator, Iterator, Union, Type, Optional
from utilmeta.utils.protocol.sse import SSEDecoder, ServerSentEvent, format_sse
from utilmeta.utils import omit
from utype.parser.rule import LogicalType
from utype.utils.compat import get_args, get_origin, is_union
from datetime import timedelta


_T = TypeVar("_T")

__all__ = [
    'SSEResponse',
    'ServerSentEvent',
    'format_sse'
]


class SSEResponse(Response[_T]):
    content_type = "text/event-stream"
    stream = True
    decoder_cls = SSEDecoder

    _event_type: Type[ServerSentEvent] = ServerSentEvent

    def __class_getitem__(cls, events):
        # SSEResponse[Event1]
        # SSEResponse[Union[Event1, Event2]]
        # SSEResponse[Event1, Event2]   # not support type hinting, but still parse as fallback

        if not isinstance(events, tuple):
            events = (events,)

        _event_types = []
        for event in events:
            origin = get_origin(event)
            if is_union(origin):
                args = get_args(event)
            else:
                args = [event]

            for arg in args:
                if isinstance(arg, type) and issubclass(arg, ServerSentEvent):
                    _event_types.append(arg)

        if not _event_types:
            return cls

        if len(_event_types) == 1:
            event_type = _event_types[0]
            response_name = event_type.__name__
        else:
            # event_type = Union[tuple(_event_types)]
            event_type = LogicalType.any_of(*_event_types)
            response_name = '_'.join(['union'] + [t.__name__ for t in _event_types])

        class _response(cls):
            _event_type = event_type

        _response.__name__ = f'{cls.__name__}_{response_name}'
        _response.__qualname__ = ".".join(
            cls.__qualname__.split(".")[:-1] + [_response.__name__]
        )

        return _response

    def __init_subclass__(cls, **kwargs):
        # do noting
        pass

    def __init__(
        self,
        event_stream: Union[Iterator, AsyncIterator] = None,
        chunk_size: Optional[int] = None,
        cache_events: bool = False,
        # timeout: Union[int, float, timedelta] = None,
        **kwargs
    ):
        super().__init__(event_stream=event_stream, **kwargs)
        # if isinstance(timeout, timedelta):
        #     timeout = timeout.total_seconds()
        #
        # self.timeout = timeout
        self.chunk_size = chunk_size
        self._decoder = self.decoder_cls()
        self._iterator = None
        self._async_iterator = None
        self._cache_events = cache_events
        self._events = []

    @property
    def content(self):
        events = []
        for event in self:
            events.append(event)
        return events

    def _iter_events(self) -> Iterator[ServerSentEvent]:
        if self.event_stream:
            if inspect.isasyncgen(self.event_stream):
                raise RuntimeError(f'Event stream is async generator, please use aiter')
            for event in self.event_stream:
                yield self._decoder.decode(event)
        elif self.is_event_stream:
            yield from self._decoder.iter_bytes(self.adaptor.iter_bytes(self.chunk_size))

    async def _aiter_events(self) -> AsyncIterator[ServerSentEvent]:
        if self.event_stream:
            if inspect.isasyncgen(self.event_stream):
                async for event in self.event_stream:
                    yield self._decoder.decode(event)
            else:
                for event in self.event_stream:
                    yield self._decoder.decode(event)
        elif self.is_event_stream:
            try:
                async for event in self._decoder.aiter_bytes(self.adaptor.aiter_bytes(self.chunk_size)):
                    yield event
            except NotImplementedError:
                for event in self._decoder.iter_bytes(self.adaptor.iter_bytes(self.chunk_size)):
                    yield event

    def parse_event(self, event: ServerSentEvent, fail_silently: bool = True) -> _T:
        if isinstance(event, self._event_type):
            if self._event_type == ServerSentEvent or event.__class__ != ServerSentEvent:
                # prevent Union[..., ServerSentEvent] from catching here
                return event
        try:
            if isinstance(self._event_type, LogicalType):
                target_event = None
                for arg in self._event_type.args:
                    if isinstance(arg, type) and issubclass(arg, ServerSentEvent):
                        field = arg.__parser__.get_field('event')
                        if field and field.default == event.event:
                            target_event = arg
                            break
                if target_event:
                    event = target_event(**event)
                else:
                    event = self._event_type(event)
            else:
                event = self._event_type(**event)
        except Exception as e:
            if fail_silently:
                event.set_parse_error(e)
            else:
                raise
        return event

    def _init_iterator(self, fail_silently: bool = True) -> Iterator[_T]:
        try:
            for event in self._events:
                # cached events
                yield event
            iterator = self._iter_events()
            for event in iterator:
                if not isinstance(event, ServerSentEvent):
                    continue
                if event.event == 'close':
                    break
                # elif event.event == 'error':
                #     pass
                event = self.parse_event(event, fail_silently=fail_silently)
                if self._cache_events:
                    self._events.append(event)
                yield event
            # Ensure the entire stream is consumed
            for _ in iterator:
                ...
        finally:
            self.close()

    async def _init_async_iterator(self, fail_silently: bool = True) -> AsyncIterator[_T]:
        try:
            for event in self._events:
                # cached events
                yield event
            iterator = self._aiter_events()
            async for event in iterator:
                if not isinstance(event, ServerSentEvent):
                    continue
                if event.event == 'close':
                    break
                # elif event.event == 'error':
                #     pass
                event = self.parse_event(event, fail_silently=fail_silently)
                if self._cache_events:
                    self._events.append(event)
                yield event
            # Ensure the entire stream is consumed
            async for _ in iterator:
                ...
        finally:
            await self.aclose()

    def __iter__(self) -> Iterator[_T]:
        if self._iterator is None:
            self._iterator = self._init_iterator()
        for event in self._iterator:
            yield event

    def __next__(self) -> _T:
        if self._iterator is None:
            self._iterator = self._init_iterator()
        return self._iterator.__next__()

    async def __aiter__(self) -> AsyncIterator[_T]:
        if self._async_iterator is None:
            self._async_iterator = self._init_async_iterator()
        async for event in self._async_iterator:
            yield event

    async def __anext__(self) -> _T:
        if self._async_iterator is None:
            self._async_iterator = self._init_async_iterator()
        return await self._async_iterator.__anext__()

    def iter(
        self,
        read_timeout=None,
        total_timeout=None,
        raise_timeout: bool = False
    ):
        # if not raise timeout, timeout will be wrapped to a [event: error, data: timeout: true] event
        if isinstance(read_timeout, timedelta):
            read_timeout = read_timeout.total_seconds()
        if isinstance(total_timeout, timedelta):
            total_timeout = total_timeout.total_seconds()

        if read_timeout or total_timeout:
            gen = self.__iter__()
            import multiprocessing.pool
            import time

            start = time.monotonic()
            closed = False

            def next_with_timeout():
                pool = multiprocessing.pool.ThreadPool(processes=1)
                async_result = pool.apply_async(gen.__next__)
                elapsed = time.monotonic() - start
                remaining = max(0.0, total_timeout - elapsed) if total_timeout else None
                curr_read_timeout = min(read_timeout, remaining) if read_timeout else remaining

                try:
                    if remaining == 0:
                        raise multiprocessing.context.TimeoutError
                    r = async_result.get(curr_read_timeout)
                except multiprocessing.context.TimeoutError:
                    # pool.terminate()
                    if total_timeout:
                        msg = f"{self} read events timed out after {total_timeout} seconds"
                    else:
                        msg = f"{self} read event timed out after {read_timeout} seconds"

                    if raise_timeout:
                        raise TimeoutError(msg)

                    nonlocal closed
                    closed = True
                    return ServerSentEvent(
                        event='error',
                        data={
                            'timeout': True,
                            'read_timeout': read_timeout,
                            'total_timeout': total_timeout,
                            'total_time': elapsed,
                            'message': msg
                        }
                    )

                finally:
                    pool.close()
                return r

            try:
                while True:
                    if closed:
                        break
                    yield next_with_timeout()
            except StopIteration:
                return
            finally:
                # requests .close() will wait until response is read done
                omit(self.close)()
        else:
            yield from self

    async def aiter(
        self,
        read_timeout=None,
        total_timeout=None,
        raise_timeout: bool = False
    ):
        if isinstance(read_timeout, timedelta):
            read_timeout = read_timeout.total_seconds()
        if isinstance(total_timeout, timedelta):
            total_timeout = total_timeout.total_seconds()

        if read_timeout or total_timeout:
            agen = self.__aiter__()

            import asyncio
            import time

            start = time.monotonic()
            closed = False

            async def next_with_timeout():
                elapsed = time.monotonic() - start
                remaining = max(0.0, total_timeout - elapsed) if total_timeout else None
                curr_read_timeout = min(read_timeout, remaining) if read_timeout else remaining

                try:
                    if remaining == 0:
                        raise asyncio.TimeoutError

                    return await asyncio.wait_for(agen.__anext__(), curr_read_timeout)
                except asyncio.TimeoutError:
                    if total_timeout:
                        msg = f"{self} read events timed out after {total_timeout} seconds"
                    else:
                        msg = f"{self} read event timed out after {read_timeout} seconds"
                    if raise_timeout:
                        raise TimeoutError(msg)
                    nonlocal closed
                    closed = True
                    return ServerSentEvent(
                        event='error',
                        data={
                            'timeout': True,
                            'read_timeout': read_timeout,
                            'total_timeout': total_timeout,
                            'total_time': elapsed,
                            'message': msg
                        }
                    )

            try:
                while True:
                    if closed:
                        break
                    yield await next_with_timeout()
            except StopAsyncIteration:
                return
            finally:
                await self.aclose()

        else:
            async for event in self:
                yield event
