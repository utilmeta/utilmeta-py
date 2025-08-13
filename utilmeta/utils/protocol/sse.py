import json
from typing import Any, TypeVar, Iterator, AsyncIterator, Optional, List
import utype
from utype import Schema
from utilmeta.utils import json_dumps


_T = TypeVar("_T")


def format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json_dumps(data)}\n\n"


class ServerSentEvent(Schema):
    event: Optional[str] = utype.Field(default=None, defer_default=True)
    data: Any = utype.Field(default=None, defer_default=True)
    id: Optional[str] = utype.Field(default=None, defer_default=True)
    retry: Optional[int] = utype.Field(default=None, defer_default=True)

    def __init__(
        self,
        *,
        event: Optional[str] = None,
        data=None,
        id: Optional[str] = None,
        retry: Optional[int] = None,
    ):
        if data is None:
            data = ""
        if not event and not data:
            raise ValueError(f'event or data of {self.__class__} is required')
        self._parse_error = None

        super().__init__(locals())

    def json(self) -> Any:
        if not self.data:
            return None
        return json.loads(self.data)

    def __str__(self) -> str:
        lines = []
        if self.event is not None:
            lines.append(f"event: {self.event}")
        if self.data is not None:
            # SSE 允许多行 data，每行都要加 'data: '
            data_str = json_dumps(self.data) if isinstance(self.data, (dict, list)) else str(self.data)
            for line in data_str.splitlines():
                lines.append(f"data: {line}")
        if self.id is not None:
            lines.append(f"id: {self.id}")
        if self.retry is not None:
            lines.append(f"retry: {self.retry}")
        return "\n".join(lines) + "\n\n"

    def encode(self, *args, **kwargs) -> bytes:
        return str(self).encode(*args, **kwargs)

    @property
    @utype.Field(no_output=True)
    def parse_error(self) -> Optional[Exception]:
        return self._parse_error

    def set_parse_error(self, error: Exception):
        self._parse_error = error


class SSEDecoder:
    _data: List[str]
    _event: Optional[str]
    _retry: Optional[int]
    _last_event_id: Optional[str]

    def __init__(self) -> None:
        self._event = None
        self._data = []
        self._last_event_id = None
        self._retry = None

    def iter_bytes(self, iterator: Iterator[bytes]) -> Iterator[ServerSentEvent]:
        """Given an iterator that yields raw binary data, iterate over it & yield every event encountered"""
        for chunk in self._iter_chunks(iterator):
            # Split before decoding so splitlines() only uses \r and \n
            for raw_line in chunk.splitlines():
                line = raw_line.decode("utf-8")
                sse = self.decode(line)
                if sse:
                    yield sse

    def _iter_chunks(self, iterator: Iterator[bytes]) -> Iterator[bytes]:
        """Given an iterator that yields raw binary data, iterate over it and yield individual SSE chunks"""
        data = b""
        for chunk in iterator:
            for line in chunk.splitlines(keepends=True):
                data += line
                if data.endswith((b"\r\r", b"\n\n", b"\r\n\r\n")):
                    yield data
                    data = b""
        if data:
            yield data

    async def aiter_bytes(self, iterator: AsyncIterator[bytes]) -> AsyncIterator[ServerSentEvent]:
        """Given an iterator that yields raw binary data, iterate over it & yield every event encountered"""
        async for chunk in self._aiter_chunks(iterator):
            # Split before decoding so splitlines() only uses \r and \n
            for raw_line in chunk.splitlines():
                line = raw_line.decode("utf-8")
                sse = self.decode(line)
                if sse:
                    yield sse

    async def _aiter_chunks(self, iterator: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        """Given an iterator that yields raw binary data, iterate over it and yield individual SSE chunks"""
        data = b""
        async for chunk in iterator:
            for line in chunk.splitlines(keepends=True):
                data += line
                if data.endswith((b"\r\r", b"\n\n", b"\r\n\r\n")):
                    yield data
                    data = b""
        if data:
            yield data

    def decode(self, line: str) -> Optional[ServerSentEvent]:
        if not line:
            if not self._event and not self._data and not self._last_event_id and self._retry is None:
                return None

            sse = ServerSentEvent(
                event=self._event,
                data="\n".join(self._data),
                id=self._last_event_id,
                retry=self._retry,
            )

            # NOTE: as per the SSE spec, do not reset last_event_id.
            self._event = None
            self._data = []
            self._retry = None

            return sse

        if line.startswith(":"):
            return None

        fieldname, _, value = line.partition(":")

        if value.startswith(" "):
            value = value[1:]

        if fieldname == "event":
            self._event = value
        elif fieldname == "data":
            self._data.append(value)
        elif fieldname == "id":
            if "\0" in value:
                pass
            else:
                self._last_event_id = value
        elif fieldname == "retry":
            try:
                self._retry = int(value)
            except (TypeError, ValueError):
                pass
        else:
            pass  # Field is ignored.

        return None
