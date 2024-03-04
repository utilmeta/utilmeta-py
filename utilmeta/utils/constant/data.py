from ..datastructure import Static

SECRET = '*' * 8
PY = '.py'
ID = 'id'
PK = 'pk'
SEG = '__'
UTF_8 = 'utf-8'
SHA_256 = 'sha256'
ELEMENTS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
MAX_BASE = len(ELEMENTS)


class Logic(Static):
    ALL = '*'
    AND = '&'
    OR = '|'
    XOR = '^'
    NOT = '~'


class Reg(Static):
    META = '.^$#~&*+?{}[]\\|()'
    IP = '((2(5[0-5]|[0-4]\\d))|[0-1]?\\d{1,2})(\\.((2(5[0-5]|[0-4]\\d))|[0-1]?\\d{1,2})){3}'
    ALNUM = '[0-9a-zA-Z]+'
    ALNUM_SCORE = '[0-9a-zA-Z_]+'
    ALNUM_SEP = '[0-9a-zA-Z-]+'
    ALNUM_SCORE_SEP = '[0-9a-zA-Z_-]+'

    ALL = '.+'
    URL_ROUTE = '[^/]+'  # match all string except /
    PATH_REGEX = '{(%s)}' % ALNUM_SCORE
    # EMAIL_FULL = '^(?:[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~-]+(?:\\.[a-zA-Z0-9!#$%&\'' \
    #         '*+/=?^_`{|}~-]+)*|(?:[\x01-\x08\x0b\x0c\x0e-\x1f!#-[]-' \
    #         '\x7f]|\\[\x01-\t\x0b\x0c\x0e-\x7f])*)@(?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]' \
    #         '*[a-zA-Z0-9])?\\.)+[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?|\\[(?:(?:(2(5[0-5]|' \
    #         '[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9]))\\.){3}(?:(2(5[0-5]|[0-4][0-9])' \
    #         '|1[0-9][0-9]|[1-9]?[0-9])|[a-zA-Z0-9-]*[a-zA-Z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f' \
    #         '!-ZS-\x7f]|\\[\x01-\t\x0b\x0c\x0e-\x7f])+)\\])&'
    EMAIL_ALNUM = '^[a-zA-Z0-9]+@[a-zA-Z0-9]+(\\.[a-zA-Z0-9]+)+[a-z0-9A-Z]+$'
    EMAIL = '^[a-z0-9A-Z]+[a-z0-9A-Z._-]+@[a-zA-Z0-9_-]+(\\.[a-zA-Z0-9_-]+)+[a-z0-9A-Z]+$'
    EMAIL_SIMPLE = '^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$'

    must_contains_letter_number = '(?=.*[0-9])(?=.*[a-zA-Z]).+'
    must_contains_letter_number_special = r'(?=.*[0-9])(?=.*[a-zA-Z])(?=.*[^a-zA-Z0-9]).+'
    must_contains_hybrid_letter_number_special = '(?=.*[0-9])(?=.*[A-Z])(?=.*[a-z])(?=.*[^a-zA-Z0-9]).+'


class DateFormat(Static):
    DATETIME = "%Y-%m-%d %H:%M:%S"
    DATETIME_DF = '%Y-%m-%d %H:%M:%S.%f'
    DATETIME_F = '%Y-%m-%d %H:%M:%S %f'
    DATETIME_P = '%Y-%m-%d %I:%M:%S %p'
    DATETIME_T = "%Y-%m-%dT%H:%M:%S"
    DATETIME_TZ = "%Y-%m-%dT%H:%M:%SZ"
    DATETIME_TFZ = "%Y-%m-%dT%H:%M:%S.%fZ"
    DATETIME_TF = "%Y-%m-%dT%H:%M:%S.%f"
    DATETIME_ISO = "%Y-%m-%dT%H:%M:%S.%fTZD"
    DATETIME_GMT = '%a, %d %b %Y %H:%M:%S GMT'
    DATETIME_PS = '%a %b %d %H:%M:%S %Y'
    DATETIME_GMT2 = '%b %d %H:%M:%S %Y GMT'
    DATE = '%Y-%m-%d'
    # TIME = '%H:%M:%S'


class Key(Static):
    USER_ID = '_user_id'
    IP_KEY = '_ip'
    UA_KEY = '_ua'

    USER_HASH = '_user_hash'
    USER_CACHE = '_cached_user'
    PK_LIST = '_pk_list'

    DATA = '_data'
    HINTS = '_hints'
    Q = '_q'
    ID = '_id'
    MERGE = '_merge'
    META = '_meta'
    ROUTER = '_Router'
    DISABLE_CACHE = '_disable_cache'
    INSTANCE = '_instance'


class Attr(Static):
    GT = '__gt__'
    GE = '__ge__'
    LT = '__lt__'
    LE = '__le__'

    NEXT = '__next__'
    COMMAND = '__command__'
    SPEC = '__spec__'
    LEN = '__len__'
    DOC = '__doc__'
    HASH = '__hash__'
    CODE = '__code__'
    MODULE = '__module__'
    BASES = '__bases__'
    NAME = '__name__'
    FUNC = '__func__'
    CALL = '__call__'
    ARGS = '__args__'
    INIT = '__init__'
    DICT = '__dict__'
    MAIN = '__main__'
    ITER = '__iter__'
    LOCK = '__locked__'
    INNER = '__inner__'
    PROXY = '__proxy__'
    RELATED = '__related__'
    STATUS = '__status__'
    ORIGIN = '__origin__'
    TARGET = '__target__'
    CATEGORY = '__category__'
    CAUSES = '__causes__'
    CAUSE = '__cause__'
    CLS = '__class__'
    PARSER = '__parser__'
    BUILTINS = '__builtins__'
    ANNOTATES = '__annotations__'
    ISOLATE = '__isolate__'
    CONFIG = '__config__'
    OPTIONS = '__options__'
    CACHE = '__cache__'
    VACUUM = '__vacuum__'
    VALIDATE = '__validate__'
    TEMPLATE = '__template__'
    DATA = '__data__'
    EXTRA = '__extra__'
    ADD = '__ADD__'
    MOD = '__MOD__'
    REM = '__REM__'

    GETATTR = '__getattr__'
    GETATTRIBUTE = '__getattribute__'

    GET = '__get__'
    SET = '__set__'
    DELETE = '__delete__'


class EndpointAttr(Static):
    method = 'method'
    alias = 'alias'
    hook = 'hook'

    main = 'main'
    unit = 'unit'

    before_hook = 'before_hook'
    after_hook = 'after_hook'
    error_hook = 'error_hook'
    errors = 'errors'
    excludes = 'excludes'


ATOM_TYPES = (str, int, bool, float, type(None))
JSON_TYPES = (*ATOM_TYPES, list, dict)
# types thar can directly dump to json
COMMON_TYPES = (*JSON_TYPES, set, tuple, bytes)
COMMON_ERRORS = (AttributeError, TypeError, ValueError, IndexError, KeyError, UnicodeDecodeError)
HOOK_TYPES = (EndpointAttr.before_hook, EndpointAttr.after_hook, EndpointAttr.error_hook)
UNIT_TYPES = (EndpointAttr.main, *HOOK_TYPES)
DEFAULT_SECRET_NAMES = (
    'password',
    'secret',
    'dsn',
    'sessionid',
    'pwd',
    'passphrase',
    '_token',
    '_key',
)
