from ..datastructure import Static
import re

SCHEME = "://"
LOCAL = "localhost"
LOCAL_IP = "127.0.0.1"
ALL_IP = "0.0.0.0"
PATH_REGEX = re.compile("{([a-zA-Z][a-zA-Z0-9_]*)}")


class HTTPMethod(Static):
    GET = "GET"
    PUT = "PUT"
    POST = "POST"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    TRACE = "TRACE"
    OPTIONS = "OPTIONS"
    CONNECT = "CONNECT"


class CommonMethod(Static):
    GET = "get"
    PUT = "put"
    POST = "post"
    PATCH = "patch"
    DELETE = "delete"


class MetaMethod(Static):
    HEAD = "head"
    TRACE = "trace"
    OPTIONS = "options"
    CONNECT = "connect"


class RequestType(Static):
    PLAIN = "text/plain"
    JSON = "application/json"
    FORM_URLENCODED = "application/x-www-form-urlencoded"
    FORM_DATA = "multipart/form-data"
    XML = "text/xml"
    HTML = "text/html"
    APP_XML = "application/xml"
    OCTET_STREAM = "application/octet-stream"


class GeneralType(Static):
    JSON = "json"
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    HTML = "html"
    OCTET_STREAM = "octet-stream"

    @classmethod
    def get(cls, content_type: str):
        if not content_type:
            return None
        if "/" not in content_type:
            return content_type
        if ";" in content_type:
            content_type = content_type.split(";")[0]
        per, suf = content_type.split("/")
        if suf in GENERAL_TYPES:
            return suf
        elif per in GENERAL_TYPES:
            return per
        return cls.OCTET_STREAM

    @classmethod
    def content_type(cls, type: str):
        if ";" in type:
            type = type.split(";")[0]
        if "/" in type:
            return type
        content_map = {
            cls.HTML: "text/html",
            cls.JSON: "application/json",
            # cls.AUDIO: 'audio/*',
            # cls.VIDEO: 'video/*',
            # cls.IMAGE: 'image/*',
            # cls.TEXT: 'text/*',
            cls.OCTET_STREAM: "application/octet-stream",
        }
        return content_map.get(type)


class Scheme(Static):
    HTTP = "http"
    HTTPS = "https"
    FTP = "ftp"
    FTPS = "ftps"
    SFTP = "sftp"
    SSH = "ssh"
    WS = "ws"
    WSS = "wss"
    MQTT = "mqtt"
    SMTP = "smtp"
    POP = "pop"
    UDP = "udp"


class WebSocketEventType(Static):
    open = "open"
    close = "close"
    error = "error"
    message = "message"


class AuthScheme(Static):
    BASIC = "basic"
    DIGEST = "digest"
    BEARER = "bearer"
    TOKEN = "token"
    HOBA = "hoba"
    MUTUAL = "mutual"


class Header(Static):
    CONNECTION = "Connection"
    COOKIE = "Cookie"

    REMOTE_ADDR = "REMOTE_ADDR"
    FORWARDED_FOR = "HTTP_X_FORWARDED_FOR"
    AUTHORIZATION = "Authorization"

    WWW_AUTH = "WWW-Authenticate"

    ACCEPT = "Accept"
    ACCEPT_LANGUAGE = "Accept-Language"
    ACCEPT_ENCODING = "Accept-Encoding"
    CONTENT_LANGUAGE = "Content-Language"

    REFERER = "Referer"
    UPGRADE = "Upgrade"

    SET_COOKIE = "Set-Cookie"
    USER_AGENT = "User-Agent"

    VARY = "Vary"
    EXPIRES = "Expires"
    PRAGMA = "Pragma"
    CACHE_CONTROL = "Cache-Control"
    ETAG = "Etag"
    LAST_MODIFIED = "Last-Modified"

    IF_UNMODIFIED_SINCE = "If-Unmodified-Since"
    IF_MODIFIED_SINCE = "If-Modified-Since"
    IF_NONE_MATCH = "If-None-Match"
    IF_MATCH = "If-Match"

    LENGTH = "Content-Length"
    TYPE = "Content-Type"
    ALLOW = "Allow"
    ORIGIN = "Origin"
    ALLOW_ORIGIN = "Access-Control-Allow-Origin"
    ACCESS_MAX_AGE = "Access-Control-Max-Age"
    ALLOW_CREDENTIALS = "Access-Control-Allow-Credentials"
    ALLOW_METHODS = "Access-Control-Allow-Methods"
    EXPOSE_HEADERS = "Access-Control-Expose-Headers"
    ALLOW_HEADERS = "Access-Control-Allow-Headers"
    OPTIONS_METHOD = "Access-Control-Request-Method"
    OPTIONS_HEADERS = "Access-Control-Request-Headers"

    @classmethod
    def attr_name(cls, key: str):
        return key.replace("-", "_").lower()


class TCPStatus(Static):
    ESTABLISHED = "ESTABLISHED"
    SYN_SENT = "SYN_SENT"
    SYN_RECV = "SYN_RECV"
    FIN_WAIT1 = "FIN_WAIT1"
    FIN_WAIT2 = "FIN_WAIT2"
    TIME_WAIT = "TIME_WAIT"
    CLOSE = "CLOSE"
    CLOSE_WAIT = "CLOSE_WAIT"
    LAST_ACK = "LAST_ACK"
    LISTEN = "LISTEN"
    CLOSING = "CLOSING"
    NONE = "NONE"


IDLE_TCP_STATUSES = [
    TCPStatus.CLOSE,
    TCPStatus.CLOSING,
    TCPStatus.CLOSE_WAIT,
    TCPStatus.TIME_WAIT,
    TCPStatus.FIN_WAIT1,
    TCPStatus.FIN_WAIT2,
    TCPStatus.LAST_ACK,
]
HTTP = Scheme.HTTP + SCHEME
HTTPS = Scheme.HTTPS + SCHEME
REQUEST_TYPES = RequestType.gen()
CONTENT_TYPE = Header.attr_name(Header.TYPE)
DICT_TYPES = (
    RequestType.JSON,
    RequestType.XML,
    RequestType.FORM_URLENCODED,
    RequestType.FORM_DATA,
)
GENERAL_TYPES = GeneralType.gen()
STREAM_TYPES = (
    GeneralType.IMAGE,
    GeneralType.AUDIO,
    GeneralType.VIDEO,
    GeneralType.OCTET_STREAM,
)
SCHEMES = Scheme.gen()
ALLOW_HEADERS = (Header.TYPE, Header.LENGTH, Header.ORIGIN)
HTTP_METHODS = HTTPMethod.gen()
ISOLATED_HEADERS = {Header.LENGTH, Header.TYPE, Header.CONNECTION}
SAFE_METHODS = (HTTPMethod.GET, HTTPMethod.OPTIONS, HTTPMethod.HEAD, HTTPMethod.TRACE)
DEFAULT_IDEMPOTENT_METHODS = (*SAFE_METHODS, HTTPMethod.PUT, HTTPMethod.DELETE)
UNSAFE_METHODS = HAS_BODY_METHODS = (
    CommonMethod.POST,
    CommonMethod.PUT,
    CommonMethod.PATCH,
    CommonMethod.DELETE,
)
HTTP_METHODS_LOWER = [m.lower() for m in HTTP_METHODS]
COMMON_METHODS = CommonMethod.gen()
META_METHODS = MetaMethod.gen()
METHODS = COMMON_METHODS + META_METHODS
SECURE_SCHEMES = {"http": "https", "ws": "wss", "ftp": "ftps"}
STATUS_WITHOUT_BODY = (204, 205, 304)
MESSAGE_STATUSES = list(range(100, 103))
SUCCESS_STATUSES = list(range(200, 208))
REDIRECT_STATUSES = list(range(300, 308))
REQUEST_ERROR_STATUSES = (
    list(range(400, 419)) + list(range(421, 427)) + [428, 429, 431, 449, 451]
)
SERVER_ERROR_STATUSES = list(range(500, 511)) + [600]
DEFAULT_RETRY_ON_STATUSES = (408, 429, 500, 502, 503, 504)
ERROR_STATUS = {
    NotImplementedError: 501,
    Exception: 500,
    FileNotFoundError: 404,
    PermissionError: 403,
    TimeoutError: 503,
}
