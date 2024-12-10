from typing import List, Union
from utilmeta.utils.constant import Header


class HttpError(Exception):
    status: int
    append_headers: dict = None
    STATUS_EXCEPTIONS = {}
    record_disabled = False

    def __str__(self):
        msg = str(self.message or "")
        head = self.__class__.__name__
        if msg.startswith(head):
            return msg
        return f"{head}: {self.message}"

    def __init__(
        self,
        message: str = None,
        *,
        state: Union[str, int] = None,
        status: int = None,
        result=None,
        extra: dict = None,
        detail: Union[dict, list] = (),
    ):
        self.message = str(message)
        self.state = state
        self.result = result
        if status:
            self.status = status
        self.extra = extra
        self.detail = detail

    def __init_subclass__(cls, **kwargs):
        try:
            if cls.status:
                HttpError.STATUS_EXCEPTIONS.setdefault(cls.status, cls)
        except AttributeError:
            pass


class Redirect(HttpError):
    # interrupt rather than exception
    pass


class MultipleChoices(Redirect):
    status = 300


class MovePermanently(Redirect):
    status = 301


class Found(Redirect):
    status = 302


class SeeOther(Redirect):
    status = 303


class NotModified(Redirect):
    status = 304


class TemporaryRedirect(Redirect):
    status = 307


class PermanentRedirect(Redirect):
    status = 308


class RequestError(HttpError):
    status = 400


class BadRequest(RequestError):
    status = 400


class Unauthorized(RequestError):
    status = 401

    def __init__(
        self,
        message: str = None,
        *,
        state: Union[str, int] = None,
        auth_scheme: str = None,
        auth_params: dict = None,
    ):
        self.message = str(message)
        self.state = state
        super().__init__(message=message, state=state)
        if not auth_scheme:
            return
        value = auth_scheme.capitalize()
        if isinstance(auth_params, dict):
            value += " " + ",".join([f"{k}={v}" for k, v in auth_params.items()])
        self.append_headers = {Header.WWW_AUTH: value}


class PaymentRequired(RequestError):
    status = 402


class PermissionDenied(RequestError):
    status = 403

    def __init__(
        self,
        msg: str = None,
        *,
        scope=None,
        required_scope=None,
        name: str = None,
        **kwargs,
    ):
        super().__init__(msg, **kwargs)
        self.scope = scope
        self.required_scope = required_scope
        self.name = name


class NotFound(RequestError):
    status = 404

    def __init__(
        self, message: str = None, *, path: str = None, query: dict = None, **kwargs
    ):
        from urllib.parse import urlencode

        msg = [message] if message else []
        if path:
            msg.append(f"path: <{path}> not found")
        if query:
            msg.append("query: <%s> not found" % urlencode(query))
        if not msg:
            msg = ["not found"]
        self.path = path
        self.query = query
        super().__init__(message=";".join(msg), **kwargs)


class MethodNotAllowed(RequestError):
    status = 405

    def __init__(
        self, message: str = None, method: str = None, allows: List[str] = None
    ):
        self.message = (
            message or f"Method: {method} is not allowed (use methods in {allows})"
        )
        self.forbid = method
        self.allows = ", ".join([str(a) for a in allows]) if allows else ""
        self.append_headers = {Header.ALLOW: self.allows}
        super().__init__(self.message)


class NotAcceptable(RequestError):
    status = 406


class ProxyAuthenticationRequired(RequestError):
    status = 407


class RequestTimeout(RequestError):
    status = 408


class Conflict(RequestError):
    status = 409


class Gone(RequestError):
    status = 410


class LengthRequired(RequestError):
    status = 411


class PreconditionFailed(RequestError):
    status = 412


class RequestEntityTooLarge(RequestError):
    status = 413


class RequestURITooLong(RequestError):
    status = 414


class UnsupportedMediaType(RequestError):
    status = 415


class RangeNotSatisfiable(RequestError):
    status = 416


class ExpectationFailed(RequestError):
    status = 417


class ImATeapot(RequestError):
    status = 418


class MisdirectedRequest(RequestError):
    status = 421


class UnprocessableEntity(RequestError):
    status = 422


class Locked(RequestError):
    status = 423


class FailedDependency(RequestError):
    status = 424


class TooEarly(RequestError):
    status = 425


class UpgradeRequired(RequestError):
    status = 426

    def __init__(self, message: str = None, scheme: str = None):
        from utilmeta.utils.constant import Header, Scheme

        self.message = message
        self.scheme = scheme
        if scheme == Scheme.WS:
            scheme = "websocket"
        elif isinstance(scheme, str):
            scheme = scheme.upper()
        else:
            scheme = Scheme.HTTPS.upper()
        self.append_headers = {
            Header.UPGRADE: scheme,
            Header.CONNECTION: Header.UPGRADE,
        }
        super().__init__(message)


class PreconditionRequired(RequestError):
    status = 428


class TooManyRequests(RequestError):
    status = 429


class RequestHeaderFieldsTooLarge(RequestError):
    status = 431


class UnavailableForLegalReason(RequestError):
    status = 451


class ServerError(HttpError):
    status = 500

    def __init__(self, message=None, response=None):
        self.message = message
        self.response = response
        super().__init__(message=message)


class MaxRetriesExceed(ServerError, RuntimeError):
    def __init__(self, msg: str = None, max_retries: int = None):
        super().__init__(msg or f"Max retries exceeded: {max_retries}")
        self.max_retries = max_retries


class MaxRetriesTimeoutExceed(ServerError, TimeoutError):
    def __init__(self, msg: str = None, max_retries_timeout: float = None):
        super().__init__(msg or f"Max retries timeout exceeded: {max_retries_timeout}")
        self.max_retries_timeout = max_retries_timeout


class SessionRejected(RequestError):
    # an error for session IP/UA verification and allowed addresses / ua verification
    status = 403


class BadResponse(ServerError):
    status = 500

    # def __init__(self, error: str = None, response: HTTPResponse = None):
    #     self.response = response
    #     self.error = error


class InternalServerError(ServerError):
    status = 500


class NotImplementedServerError(ServerError):
    status = 501


class BadGateway(ServerError):
    status = 502


class ServiceUnavailable(ServerError):
    status = 503


class GatewayTimeout(ServerError):
    status = 504


class HTTPVersionNotSupported(ServerError):
    status = 505


class VariantAlsoNegotiates(ServerError):
    status = 506


class InsufficientStorage(ServerError):
    status = 507


class LoopDetected(ServerError):
    status = 508


class NotExtended(ServerError):
    status = 510


class NetworkAuthenticationRequired(ServerError):
    status = 511


def http_error(status: int = 400, message: str = None):
    if status < 400 or status > 600:
        raise ValueError(f"Invalid HTTP error status: {status} must in 400~600")
    error = HttpError.STATUS_EXCEPTIONS.get(status)
    if not error:

        class error(HttpError):
            pass

        error.status = status
    return error(message=message)
