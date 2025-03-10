import json
import re
import os
import math
import hashlib
from datetime import datetime, timezone
from ipaddress import ip_address
from typing import TypeVar, List, Dict, Tuple, Union, Optional
from utilmeta.utils.constant import (
    COMMON_ERRORS,
    RequestType,
    DateFormat,
    LOCAL,
    Scheme,
    SCHEME,
    HTTP,
    HTTPS,
    SCHEMES,
    UTF_8,
    AgentDevice,
    LOCAL_IP,
)
from urllib.parse import urlparse, ParseResult
from .data import based_number, multi, is_number, get_number
from .py import file_like
from utype import type_transform

T = TypeVar("T")


__all__ = [
    "http_header",
    "parse_query_dict",
    "make_header",
    "http_time",
    "retrieve_path",
    "get_domain",
    "parse_user_agents",
    "get_origin",
    "get_request_ip",
    "normalize",
    "url_join",
    "localhost",
    "private_address",
    "etag",
    "dumps",
    "loads",
    "process_url",
    "get_content_tag",
    "handle_json_float",
    "parse_raw_url",
    "json_dumps",
    "get_hostname",
    "parse_query_string",
    "encode_multipart_form",
    "valid_url",
    "encode_query",
    "is_hop_by_hop",
    "guess_mime_type",
    "fast_digest",
]


def http_time(dt: datetime, to_utc: bool = True):
    if not dt:
        return None
    if not isinstance(dt, datetime):
        dt = type_transform(dt, datetime)
    if to_utc:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime(DateFormat.DATETIME_GMT)


def guess_mime_type(path: str, strict: bool = False):
    if not path:
        return None, None
    dots = path.split(".")
    if dots:
        suffix = dots[-1]
        type_map = {
            "js": "text/javascript",
            "woff2": "font/woff2",
            "ts": "text/typescript",
        }
        if suffix in type_map:
            return type_map[suffix], None
    import mimetypes

    return mimetypes.guess_type(path, strict=strict)


def is_hop_by_hop(header_name):
    return header_name.lower() in {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }


def handle_json_float(data):
    if multi(data):
        return [handle_json_float(d) for d in data]
    elif isinstance(data, dict):
        return {key: handle_json_float(val) for key, val in data.items()}
    elif isinstance(data, float):
        if math.isnan(data):
            return None
        if data == float("inf"):
            return "Infinity"
        if data == float("-inf"):
            return "-Infinity"
    return data


def fast_digest(
    value,
    compress: Union[bool, int] = False,
    case_insensitive: bool = False,
    consistent: bool = True,
    mod: int = 2**64,
):
    if consistent:
        encoded = value if isinstance(value, bytes) else str(value).encode()
        dig_mod = int(hashlib.md5(encoded).hexdigest(), 16) % mod
        # if consistent required, we cannot use hash()
        # because every python restart will bring inconsistency to the same value hash
    else:
        dig_mod = hash(str(value)) % mod

    if compress:
        if isinstance(compress, bool):
            base = 36 if case_insensitive else 62
        elif isinstance(compress, int):
            base = compress
        else:
            raise TypeError(f"Invalid compress: {compress}")
        return based_number(dig_mod, base)
    return str(dig_mod)


def etag(data, weak: bool = False) -> str:
    if isinstance(data, str):
        if re.fullmatch(r'\A((?:W/)?"[^"]*")\Z', data):
            # data itself is etag like, guess it is another etag
            return data
    elif isinstance(data, (dict, list)):
        data = json_dumps(data)
    elif not isinstance(data, str):
        data = str(data)
    comp = fast_digest(data, compress=36, consistent=True).lower()
    quoted = f'"{comp}"'
    if weak:
        quoted = f"W/{quoted}"
    return quoted


def localhost(host: str) -> bool:
    if not isinstance(host, str):
        return False
    if "://" not in host:
        # can be http/https/unix/redis...
        host = "http://" + host
    hostname = urlparse(host).hostname
    return hostname in ["127.0.0.1", "localhost"]


def private_address(host: str, local: bool = False) -> bool:
    if not isinstance(host, str):
        return False
    if localhost(host):
        return local
    if "://" not in host:
        # can be http/https/unix/redis...
        host = "http://" + host
    hostname = urlparse(host).hostname
    from .sys import get_ip
    ip = get_ip(hostname)
    if not ip:
        return False
    try:
        return ip_address(ip).is_private
    except ValueError:
        return False


def encode_query(
    query: dict,
    exclude_null: bool = True,
    multi_bracket_suffix: bool = False,
    multi_comma_join: bool = False,
) -> str:
    if not query:
        return ""
    from urllib.parse import urlencode

    encoded = []
    for key, val in query.items():
        if val is None and exclude_null:
            continue
        if multi(val):
            if multi_comma_join:
                val = ",".join(val)
            else:
                arg = key
                if multi_bracket_suffix:
                    arg += "[]"
                encoded.extend([f"{arg}={v}" for v in val])
                continue
        encoded.append(urlencode({key: val}))
    return "&".join(encoded)


def retrieve_path(url):
    parse: ParseResult = urlparse(url)
    if parse.scheme:
        return url[len(f"{parse.scheme}{SCHEME}{parse.netloc}") :]
    if url.startswith("/"):
        return url
    return f"/{url}"


def valid_url(url: str, raise_err: bool = True, http_only: bool = True) -> str:
    url = url.strip("/").replace(" ", "")
    res = urlparse(url)
    if not res.scheme:
        if raise_err:
            raise ValueError(f"Invalid url syntax: {url}")
        return ""
    if http_only and res.scheme not in (Scheme.HTTP, Scheme.HTTPS):
        if raise_err:
            raise ValueError(f"Invalid scheme: {res.scheme}")
        return ""
    if not res.netloc:
        if raise_err:
            raise ValueError(f"empty net loc")
        return ""
    return url


def encode_multipart_form(form: dict, boundary: str = None) -> Tuple[bytes, str]:
    import binascii

    boundary = boundary or binascii.hexlify(os.urandom(16))
    if isinstance(boundary, str):
        boundary = boundary.encode("ascii")
    items = []
    for field, value in form.items():
        key = str(field).encode()
        beg = b'--%s\r\nContent-Disposition: form-data; name="%s"' % (boundary, key)
        files = value if multi(value) else [value]
        for i, val in enumerate(files):
            if file_like(val):
                content = val.read()
                if isinstance(content, str):
                    content = content.encode()
                filename = str(
                    getattr(val, "filename", None) or getattr(val, "name", None) or ""
                )
                if filename:
                    if "/" in filename or "\\" in filename:
                        filename = os.path.basename(filename)
                else:
                    filename = f"{field}-file-{i}"
                content_type = str(getattr(val, "content_type", None) or "")
                if not content_type:
                    content_type, encoding = guess_mime_type(filename)
                    if not content_type:
                        content_type = RequestType.OCTET_STREAM
                prep = b'; filename="%s"\r\nContent-Type: %s' % (
                    filename.encode(),
                    content_type.encode(),
                )
            else:
                if isinstance(val, bytes):
                    content = val
                elif isinstance(val, (dict, list)):
                    content = json_dumps(val).encode()
                else:
                    content = str(val).encode()
                prep = b""
            items.append(b"%s%s\r\n\r\n%s\r\n" % (beg, prep, content))
    body = b"".join(items) + b"--%s--\r\n" % boundary
    content_type = "multipart/form-data; boundary=%s" % boundary.decode("ascii")
    return body, content_type


# def is_file_type(content_type: str):
#     if not content_type:
#         return False
#     if '/' not in content_type:
#         return False
#     try:
#         maj, sec = content_type.split('/')
#     except ValueError:
#         return False
#     if maj in ('video', 'audio', 'image'):
#         return True
#     if sec == 'octet-stream':
#         return True
#     return False


def get_origin(
    url: str,
    with_scheme: bool = True,
    remove_www_prefix: bool = False,
    convert_port: bool = False,
    default_scheme: str = Scheme.HTTP,
    trans_local: bool = True,
):
    if not url:
        return ""
    default_scheme = str(default_scheme).lower()
    if default_scheme not in SCHEMES:
        default_scheme = Scheme.HTTP
    if not url.startswith(HTTP) and not url.startswith(HTTPS):
        url = default_scheme + SCHEME + url
    result: ParseResult = urlparse(url)
    scheme = result.scheme
    host: str = result.netloc
    port = result.port
    if convert_port:
        if port == "80":
            port = None
            if not scheme:
                scheme = Scheme.HTTP
            elif scheme != Scheme.HTTP:
                raise ValueError(f"Invalid scheme port combination: {scheme} {port}")
        if port == "443":
            port = None
            if not scheme:
                scheme = Scheme.HTTPS
            elif scheme != Scheme.HTTPS:
                raise ValueError(f"Invalid scheme port combination: {scheme} {port}")
    if remove_www_prefix:
        host = host.lstrip("www.")
    if trans_local and host.startswith(LOCAL):
        host = "127.0.0.1"
        if port:
            host = f"{host}:{port}"
    if not with_scheme:
        return host
    if not scheme:
        scheme = default_scheme
    return f"{scheme}{SCHEME}{host}"


def normalize(data, _json: bool = False):
    from utype.utils.compat import ATOM_TYPES

    if isinstance(data, ATOM_TYPES):
        return data
    import pickle

    try:
        if _json:
            raise ValueError
        pickle.dumps(data)
        return data
    except (*COMMON_ERRORS, pickle.PickleError):
        return json.loads(json_dumps(data))


def json_dumps(data, **kwargs) -> str:
    from utype import JSONEncoder

    if data is None:
        return ""
    kwargs.setdefault("cls", JSONEncoder)
    kwargs.setdefault("ensure_ascii", False)
    return json.dumps(data, **kwargs)


def dumps(data, exclude_types: Tuple[type, ...] = (), bulk_data: bool = False):
    if data is None:
        return None
    if bulk_data and isinstance(data, dict):
        return {
            key: dumps(val, exclude_types=exclude_types) for key, val in data.items()
        }
    if isinstance(data, exclude_types):
        # False / True isinstance of int, so isinstance is not accurate here
        # for incrby / decrby / incrbyfloat work fine at lua script number typed data will not be dump
        return str(data).encode()
    import pickle

    return pickle.dumps(normalize(data))


def loads(data, exclude_types: Tuple[type, ...] = (), bulk_data: bool = False):
    if data is None:
        return None
    if bulk_data and multi(data):
        return [loads(val, exclude_types=exclude_types) for val in data]
    if data is None:
        return None
    if isinstance(data, dict):
        values = {}
        for key, val in data.items():
            if isinstance(key, bytes):
                key = key.decode()
            values[key] = loads(val, exclude_types=exclude_types, bulk_data=bulk_data)
        return values
    import pickle

    try:
        return pickle.loads(data)
    except (*COMMON_ERRORS, pickle.PickleError):
        pass
    if isinstance(data, bytes):
        data = data.decode()
    if isinstance(data, exclude_types):
        return data
    if is_number(data):
        return get_number(data)
    for t in exclude_types:
        try:
            return type_transform(data, t)
        except TypeError:
            continue
    return data


def get_content_tag(body):
    if not body:
        return ""
    tag = body
    if isinstance(body, (dict, list)):
        tag = json_dumps(body).encode(UTF_8)
    elif not isinstance(body, bytes):
        tag = str(body).encode(UTF_8)
    return hashlib.sha256(tag).hexdigest()


def url_join(
    base: str,
    *routes: str,
    with_scheme: bool = True,
    prepend_slash: bool = False,
    append_slash: bool = None,
):
    if not base:
        # force convert to str
        base = ""
    route_list = []
    if not any(routes):
        if append_slash:
            if not base.endswith("/"):
                base = base + "/"
        elif append_slash is False:
            base = base.rstrip("/")
        return base
    if not isinstance(base, str):
        base = str(base) if base else ""
    final_route = base
    for route in routes:
        if not route:
            continue
        url = str(route).strip("/")
        if not url:
            continue
        final_route = str(route)
        url_res = urlparse(url)
        if url_res.scheme:
            return url
        route_list.append(url)
    end_slash = final_route.endswith("/")  # last route
    res = urlparse(base)
    if with_scheme and not res.scheme:
        raise ValueError("base url must specify a valid scheme")
    result = "/".join([base.strip("/"), *route_list])
    if not res.scheme:
        if prepend_slash:
            if not result.startswith("/"):
                result = "/" + result
        else:
            result = result.lstrip("/")
    if append_slash is not None:
        if append_slash:
            if not result.endswith("/"):
                result = result + "/"
        else:
            result = result.rstrip("/")
    elif end_slash:
        result = result + "/"
    return result


def process_url(url: Union[str, List[str]]):
    if multi(url):
        return [process_url(u) for u in url if u]
    url = url.strip("/")
    return f"/{url}/" if url else "/"


def parse_query_string(qs: str) -> dict:
    from urllib.parse import parse_qs

    return parse_query_dict(parse_qs(qs))


def parse_raw_url(url: str) -> Tuple[str, dict]:
    res = urlparse(url)
    from django.http.request import QueryDict

    return res.path, parse_query_dict(QueryDict(res.query))


def parse_query_dict(qd: Dict[str, List[str]]) -> dict:
    data = {}
    for key, val in dict(qd).items():
        if not multi(val):
            data[key] = str(val or "")
            continue
        if key.endswith("[]"):
            data[key.rstrip("[]")] = val
            continue
        if len(val) > 1:
            data[key] = val
            continue
        v = val[0]
        if v.startswith("="):
            if key.endswith(">") or key.endswith("<"):
                data[key + "="] = v[1:]
                continue
        data[key] = v or ""
    return data


def parse_user_agents(ua_string: str) -> Optional[dict]:
    if not ua_string:
        return None
    try:
        import user_agents
    except ModuleNotFoundError:
        return None
    if isinstance(ua_string, user_agents.parsers.UserAgent):
        ua = ua_string
    else:
        ua = user_agents.parse(ua_string)
    device = AgentDevice.bot
    if ua.is_bot:
        device = AgentDevice.bot
    elif ua.is_pc:
        device = AgentDevice.pc
    elif ua.is_tablet:
        device = AgentDevice.tablet
    elif ua.is_mobile:
        device = AgentDevice.mobile
    elif ua.is_email_client:
        device = AgentDevice.email
    return dict(
        browser=f"{ua.browser.family} {ua.browser.version_string}".strip(" "),
        os=f"{ua.os.family} {ua.os.version_string}".strip(" "),
        mobile=ua.is_mobile,
        bot=ua.is_bot,
        device=device,
    )


def http_header(header: str) -> str:
    h = header.upper().replace("-", "_")
    if h in {"CONTENT_TYPE", "CONTENT_LENGTH"}:
        return h
    if h.startswith("HTTP_"):
        # make idempotent
        return h
    return "HTTP_" + h


def make_header(h: T) -> T:
    """
    lower-cased _ connected variable to header
    """
    if isinstance(h, dict):
        return {make_header(key): val for key, val in h.items()}
    elif multi(h):
        return [make_header(v) for v in h]
    return "-".join([s.capitalize() for s in str(h).lower().split("_")])


def get_netloc(url: str) -> str:
    # contains port
    if not url:
        return ""
    res = urlparse(url)
    if res.netloc:
        return res.netloc
    res = urlparse(HTTP + url)
    return res.netloc


def get_hostname(url: str) -> str:
    # does not contains port
    if not url:
        return ""
    res = urlparse(url)
    if res.hostname:
        return res.hostname
    res = urlparse(HTTP + url)
    return res.hostname


def get_domain(url: str) -> Optional[str]:
    hostname = get_hostname(url)
    try:
        # is an ip address
        ip_address(hostname)
        return None
    except ValueError:
        return ".".join(hostname.split(".")[-2:])


def get_request_ip(headers: dict):
    headers = {str(k).lower().replace("_", "-"): v for k, v in headers.items()}
    ips = [
        *headers.get("x-forwarded-for", "").replace(" ", "").split(","),
        headers.get("remote-addr"),
        headers.get("x-real-ip"),
    ]
    for ip in ips:
        if not ip or ip == LOCAL_IP:
            continue
        try:
            return ip_address(ip)
        except ValueError:
            continue
    return None
