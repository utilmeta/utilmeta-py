from .. import constant
import typing
import string
import json
import re
import hashlib
import decimal
from collections import OrderedDict
from typing import List, Dict, Callable, Union, Any


__all__ = [
    'repeat', 'multi', 'duplicate',
    'pop',
    'distinct',
    'gen_key', 'order_dict', 'parse_list',
    'keys_or_args',
    'order_list', 'setval', 'dict_list',
    'regular', 'sub_regs',
    'readable',
    'readable_size',
    'make_percent',
    'restrict_keys',
    'map_dict',
    'copy_value', 'iterable', 'is_number',
    'dict_number_sum',
    'temp_diff', 'temp_patch',
    'get_arg', 'key_normalize', 'clean_line', 'camel_case',
    'distinct_add',
    'merge_list',
    'dict_number_add',
    'make_dict_by',
    'get_number', 'is_sub_dict',  'convert_data_frame',
    'based_number', 'get_based_number', 'list_or_args', 'bi_search', 'replace_null',
    'make_hash', 'avg', 'pop_null', 'dict_list_merge', 'normalize_title'
]


def normalize_title(title: str):
    return ' '.join(re.sub('\s', ' ', title).split())


def _list_dict(val):
    return isinstance(val, list) and len(val) == 1 and isinstance(val[0], dict)


def avg(values: Union[list, set, tuple], default=0):
    if not values:
        return default
    return sum(values) / len(values)


def iterable(value):
    return hasattr(value, constant.Attr.ITER)


def repeat(lst):
    return len(lst) != len(set(lst))


def dict_list(length):
    values = []
    while length:
        values.append({})
        length = length - 1
    return values


def map_dict(data: Union[list, tuple], *fields) -> Dict[str, Any]:
    return {str(f): d for d, f in zip(data, fields)}


def copy_value(data):
    """
    return a new value identical to default , but different in memory,
    to avoid multiple initialize to modify the same default data
    """
    if multi(data):
        return type(data)([copy_value(d) for d in data])
    elif isinstance(data, dict):
        return {k: copy_value(v) for k, v in data.items()}
    return data


def is_sub_dict(base: dict, sub: dict):
    for key, val in sub.items():
        if key not in base:
            return False
        if val != base[key]:
            return False
    return True


def duplicate(lst):
    _set = set(lst)
    _list = list(lst)
    for item in _set:
        _list.remove(item)
    return set(_list)


def bi_search(targets: list, val, key=lambda x: x, sort: bool = False, start: int = 0, end: int = None):
    """
    as small as possible
    """
    if not targets:
        return -1
    if sort:
        targets = sorted(targets, key=key)
    if end is None:
        end = len(targets) - 1
    if end < start:
        return -1
    v = key(val)
    if key(targets[start]) > v:
        return start - 1
    elif key(targets[end]) < v:
        return end + 1
    mid = int(start + (end - start) / 2)
    m = key(targets[mid])
    if m < v:
        if key(targets[mid + 1]) >= v:
            return mid + 1
        return bi_search(targets, val=val, key=key, start=mid + 1, end=end)
    elif m == v:
        return mid
    return bi_search(targets, val=val, key=key, start=start, end=mid - 1)


def regular(s: str) -> str:
    rs = ''
    for char in s:
        if char in constant.Reg.META:
            rs += f'\\{char}'
        else:
            rs += char
    return rs


def make_percent(val, tot, fix=1, _100=True):
    val = float(val)
    tot = float(tot)
    _min = tot
    if _100:
        val *= 100
        _min *= 100
    if tot <= 0:
        return round(float(0), fix)
    return round(min(val, _min) / tot, fix)


def multi(f):
    return isinstance(f, (list, set, frozenset, tuple, type({}.values()), type({}.keys())))


def pop(data, key, default=None):
    if isinstance(data, dict):
        return data.pop(key) if key in data else default
    elif isinstance(data, list):
        return data.pop(key) if key < len(data) else default
    return default


def make_dict_by(values: List[dict], key: str, formatter: Callable = lambda x: x) -> Dict[Any, List[dict]]:
    """
    make a dict that keys is the key value of every items in values
    make_dict_by([{'k': 1, 'v': 2}, {'k': 1, 'v': 3}, {'k': 2, 'v': 2}], key='k')
    {
        '1': [{'k': 1, 'v': 2}, {'k': 1, 'v': 3}],
        '2': [{'k': 2, 'v': 2}]
    }
    """
    if not key:
        return {}
    result: Dict[Any, List[dict]] = {}
    for val in values:
        if key not in val:
            continue
        kv = val[key]
        if kv is None:
            continue
        v = formatter(val)
        if multi(kv):
            for _k in kv:
                _k = str(_k)
                if _k in result:
                    if v not in result[_k]:
                        result[_k].append(v)
                else:
                    result[_k] = [v]
        else:
            kv = str(kv)
            if kv in result:
                if v not in result[kv]:
                    result[kv].append(v)
            else:
                result[kv] = [v]
    return result


def setval(dic, key, v, k=None, array=False):
    if array:
        dic.setdefault(key, []).append(v)
    else:
        assert k
        dic.setdefault(key, {}).update({k: v})


# def dict_overflow(base: dict, data: dict):
#     return {key: val for key, val in data.items() if key not in base}


def dict_number_add(base: dict, data: dict, nested: bool = False, flag: int = 1):
    if not base:
        return data
    if not data:
        return base
    if isinstance(base, int) and isinstance(data, int):
        return base + data
    result = {}
    for key, val in base.items():
        if key in data:
            result[key] = dict_number_add(
                val, data[key],
                nested=nested,
                flag=flag
            ) if nested else (data[key] + val * flag)
        else:
            result[key] = val
    for key, val in data.items():
        if key not in base:
            result[key] = val
    return result


def dict_list_merge(*values: dict):
    if not values:
        return {}
    result = values[0]
    if not isinstance(result, dict):
        result = {}
    for val in values[1:]:
        if isinstance(val, dict):
            result.update(val)
        elif multi(val):
            result.update(dict_list_merge(*val))
    return result


def dict_number_sum(*values: dict, nested: bool = False):
    if len(values) == 1 and multi(values[0]):
        return dict_number_sum(*values[0], nested=nested)
    result = {}
    for val in values:
        if isinstance(val, dict):
            result = dict_number_add(result, val, nested=nested)
    return result


def pop_null(data):
    if multi(data):
        return [pop_null(d) for d in data]
    elif isinstance(data, dict):
        for k in list(data):
            if data[k] is None:
                data.pop(k)
        return data
    return data


def order_list(data: list, orders: list, by: str, join_rest: bool = False) -> list:
    result = []
    if len(data) <= 1 or not orders:
        return data
    for i in orders:
        for d in data:
            d: dict
            if str(d.get(by)) == str(i):
                result.append(d)
                data.remove(d)
                break
    if join_rest:
        result += data  # if there is remaining data left, join the result
    return result


def order_dict(data: dict, orders: tuple) -> OrderedDict:
    # consider the origin data is already ordered (odict_items)
    return OrderedDict(sorted(list(data.items()), key=lambda item: orders.index(item[0]) if item[0] in orders else 0))


def distinct(data: list, key: str = None, val_type: type = None) -> list:
    if not data:
        return []
    if not multi(data):
        return [data]
    data = list(data)
    result = []
    values = []
    for d in data:
        if val_type:
            d = val_type(d)
        if key:
            val = d.get(key)
            if val not in values:
                values.append(val)
                result.append(d)
        elif d not in result:
            result.append(d)
    return result


def is_number(s):
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def get_number(num_str: str, ignore: bool = True) -> Union[int, float, None]:
    if isinstance(num_str, (int, float, decimal.Decimal)):
        return num_str
    try:
        value = float(num_str)
    except (ValueError, TypeError):
        if ignore:
            return None
        raise TypeError(f'Invalid number: {num_str}')
    else:
        if value.is_integer():
            return int(value)
        return value


def readable(data, max_length: int = 20, more: bool = True) -> str:
    if data is None:
        return repr(None)
    _bytes = False
    if isinstance(data, bytes):
        _bytes = True
        data = data.decode('utf-8', 'ignore')
    if multi(data):
        # if not rep:
        #     if len(str(data)) <= max_length:
        #         return str(data)
        #     return str(data)[:max_length] + ('...' if more else '')
        form = {list: '[%s]', tuple: '(%s)', set: '{%s}'}
        items = []
        total = 0
        for d in data:
            total += len(repr(d))
            if total > max_length:
                items.append(f'...({len(data)} items)' if more else '')
                break
            items.append(repr(d))
        for t, fmt in form.items():
            if isinstance(data, t):
                return fmt % ', '.join(items)
        return '[%s]' % ', '.join(items)
    elif isinstance(data, dict):
        # if not rep:
        #     if len(str(data)) <= max_length:
        #         return str(data)
        #     return str(data)[:max_length] + '...'
        items = []
        total = 0
        for k, v in data.items():
            total += len(str(k)) + len(str(v)) + 2
            if total > max_length:
                items.append(f'...({len(data)} items)' if more else '')
                break
            items.append(repr(k) + ': ' + repr(v))
        return '{%s}' % ', '.join(items)
    elif is_number(data):
        return str(data)
    if not isinstance(data, str):
        from .py import represent
        return represent(data)
    excess = len(data) - max_length
    if excess >= 0:
        data = data[:max_length] + (f'...({excess} more chars)' if more else '')
    result = repr(data)
    if _bytes:
        result = 'b' + result
    return result


def readable_size(size, depth=0):
    unit = ['B', 'KB', 'MB', 'GB', 'TB']
    if size < 1 or not size:
        return f"0 {unit[depth]}"
    if 1 <= size < 1000:
        return f'{str(size)} {unit[depth]}'
    return readable_size(int(size/1024), depth+1)


def parse_list(data, merge=False, distinct_merge=None, merge_type: type = None) -> Union[list, tuple]:
    if multi(data):
        if merge:
            result = []
            multi_occur = False
            for d in data:
                if multi(d):
                    multi_occur = True
                    result += parse_list(d, merge_type=merge_type, merge=True, distinct_merge=distinct_merge)
                else:
                    if merge_type:
                        from utype import type_transform
                        d = type_transform(d, merge_type)
                    result.append(d)
            if distinct_merge is None and multi_occur:
                distinct_merge = True
            if distinct_merge:
                try:
                    return list(set(result))
                except TypeError:
                    return result
            return result
        return list(data)
    elif not data:
        return []
    elif type(data) == str:
        def start_end(value: str, start, end=None):
            if end is None:
                end = start
            return value.startswith(start) and value.endswith(end)

        data: str
        maybe_list = start_end(data, '[', ']')
        maybe_tuple = start_end(data, '(', ')')
        maybe_json = start_end(data, '{', '}')
        spliter = ';' if ';' in data else ','
        if maybe_tuple:
            return tuple([v.strip() for v in data.lstrip('(').rstrip(')').split(spliter)])
        if maybe_list or maybe_json:
            try:
                return parse_list(json.loads(data, strict=False), merge=merge)
            except json.JSONDecodeError:
                pass
        elif spliter in data:
            return [v.strip() for v in data.strip().split(spliter)]
    elif not isinstance(data, constant.COMMON_TYPES) and iterable(data):
        return parse_list(list(data), merge=merge, distinct_merge=distinct_merge, merge_type=merge_type)
    return [data]


def key_normalize(key: str) -> str:
    from .py import valid_attr
    if not key:
        return ''
    key = key.lower()
    if '-' in key:
        # probably header
        key = key.replace('-', '_')
    if valid_attr(key):
        return key
    if key.isdigit():
        return 'arg_' + key

    # if key in constant.NOTE_MAP:
    #     return f'{constant.NOTE_MAP[key]}_'      # use suffix instead of prefix
    # try:
    #     return Filter.normalize(key)
    # except constant.COMMON_ERRORS:
    new_key = ''
    for i, c in enumerate(key):
        if c.isalnum():
            new_key += c
        elif c == '.':
            new_key += '__'
        elif c == '-':
            new_key += '_'
        elif c == '_':
            new_key += c
        elif c in ('>', '<'):
            if i == len(key) - 2 and key[i+1] == '=':
                new_key += f'__{constant.NOTE_MAP[c]}e'
                break
            new_key += f'__{constant.NOTE_MAP[c]}'
        else:
            new_key += '__' + constant.NOTE_MAP.get(c, '')
    return new_key


def camel_case(name: str, reverse: bool = False) -> str:
    cap = True
    s = ''
    for i, c in enumerate(name):
        if reverse:
            if c.isupper():
                if i:
                    # not for first upper case
                    s += '_'
                c = c.lower()
        else:
            if c == '_':
                cap = True
                continue
            if cap:
                c = c.upper()
                cap = False
        s += c
    return s


def clean_line(line: str):
    return line.replace('\t', '').replace('\n', '').replace(' ', '')


def sub_regs(reg: str) -> typing.Tuple[tuple, dict]:
    left_p = 0
    right_p = 0
    sub = None
    ls = 0
    ps = []
    for i, s in enumerate(reg):
        if s == '(':
            if i and reg[i-1] == '\\':
                continue
            if sub is not None:
                continue
            if not left_p:
                ls = i
            left_p += 1
        elif s == ')':
            if i and reg[i-1] == '\\':
                continue
            if sub is not None:
                continue
            right_p += 1
        elif s == '[':
            sub = i
        elif s == ']':
            sub = None
        if left_p == right_p and left_p > 0:
            ps.append(reg[ls+1:i])
            left_p = 0
            right_p = 0
    args = []
    kwargs = {}
    kw_reg = '\\?P<([A-Za-z0-9_-]+)>(.+)'
    for p in ps:
        match = re.search(kw_reg, p)
        if match:
            key, reg = match.groups()
            kwargs[key] = reg
        else:
            args.append(p)
    return tuple(args), kwargs


def based_number(num: int, base: int = 10) -> str:
    num, base = int(num), int(base)
    n = abs(num)
    if base <= 1 or base > len(constant.ELEMENTS):
        raise ValueError(f'number base should > 1 and <= {len(constant.ELEMENTS)}')
    if base == 10:
        return str(n)
    # values = []
    output = ''
    elements = constant.ELEMENTS[0:base]
    while n:
        i = n % base
        n = n // base
        output = elements[i] + output
        # values.append(elements[i])
    # values.reverse()
    # return ''.join(values)
    return output


def get_based_number(num: Union[str, int], from_base: int, to_base: int = 10) -> str:
    if from_base <= 36:
        return based_number(int(num, base=from_base), base=to_base)
    if from_base > len(constant.ELEMENTS):
        raise ValueError(f'number base should > 1 and < {len(constant.ELEMENTS)}')
    num = str(num).lstrip('-')
    value = 0
    for i, n in enumerate(num):
        value += constant.ELEMENTS.index(n) * from_base ** (len(num) - i - 1)
    return based_number(value, base=to_base)


def get_arg(args: List[str], key: str, *, sole: bool = False, remove: bool = True):
    # if key.startswith('--'):
    #     for arg in args:
    #         if arg.startswith(key + '='):
    #             return arg.lstrip(key + '=')
    #     return None
    if sole:
        if key in args:
            if remove:
                args.remove(key)
            return True
        return False
    try:
        arg = args[args.index(key) + 1]
        if remove:
            args.remove(key)
            args.remove(arg)
        return arg
    except (IndexError, ValueError):
        return None


def keys_or_args(args=None, *keys) -> list:
    """
    this function can work will only if target item is not multi-valued
    """
    if multi(args):
        args = list(args)
    elif args:
        args = [args]
    else:
        args = []
    for key in keys:
        if multi(key):
            args.extend(key)
        else:
            args.append(key)
    return args


def list_or_args(keys, args: tuple):
    # returns a single new list combining keys and args
    try:
        iter(keys)
        # a string or bytes instance can be iterated, but indicates
        # keys wasn't passed as a list
        if isinstance(keys, (str, bytes)):
            keys = [keys]
        else:
            keys = list(keys)
    except TypeError:
        keys = [keys]
    if args:
        keys.extend(args)
    return keys


def distinct_add(target: list, data):
    if not data:
        return target
    if not isinstance(target, list):
        raise TypeError(f'Invalid distinct_add target type: {type(target)}, must be lsit')
    # target = list(target)
    if not multi(data):
        if data not in target:
            target.append(data)
        return target
    for item in data:
        if item not in target:
            target.append(item)
    return target


def replace_null(data: dict, default=0):
    return {key: val or default for key, val in data.items()}


def temp_patch(base: dict, *updates: dict):
    def patch(b: dict, p: dict):
        pop(p, constant.Attr.MOD)
        for r in pop(p, constant.Attr.REM, []):
            pop(b, r)
        for k in list(b.keys()):
            v = b[k]
            if k in p:
                if isinstance(v, dict) and isinstance(p[k], dict):
                    patch(v, p[k])
                elif _list_dict(v) and _list_dict(p[k]):
                    patch(v[0], p[k][0])
                else:
                    b[k] = p[k]
                p.pop(k)  # do not update this k at b
        b.update(p)

    for update in updates:
        patch(base, update)
    return base


def temp_diff(base: dict, temp: dict):
    """
         each time a new service is generated, this method will be used
         to compare the difference between the old root template and new one,
         to tell the add/remove/modify of the api system, to support API version control system
    """
    p = {}
    for k, v in temp.items():
        if k not in base:
            p[k] = v
        elif isinstance(v, dict) and isinstance(base[k], dict):
            df = temp_diff(base[k], v)
            if df:
                p[k] = df
        elif _list_dict(v) and _list_dict(base[k]):
            df = temp_diff(base[k][0], v[0])
            if df:
                p[k] = [df]
        else:
            if base[k] != v:
                p[k] = v
                setval(p, constant.Attr.MOD, v=k, array=True)
    for k, v in base.items():
        if k not in temp:
            setval(p, constant.Attr.REM, v=k, array=True)
    return p


def make_hash(value: str, seed: str = '', mod: int = 2 ** 32):
    return int(hashlib.md5((str(value) + str(seed or '')).encode()).hexdigest(), 16) % mod


def restrict_keys(keys: Union[list, tuple, set], data: dict, default=None) -> dict:
    for key in set(data).difference(keys):
        data.pop(key)
    for key in set(keys).difference(data):
        data[key] = default
    return data


def merge_list(*lst, keys=None) -> List[dict]:
    result = []
    for items in zip(*[ls for ls in lst if ls]):
        val = {}
        for item in items:
            val.update(item)
        result.append(restrict_keys(keys=keys, data=val) if keys else val)
    return result


def convert_data_frame(data: List[dict], align: bool = False, depth: int = 1, keys: List[str] = ()) -> Dict[str, list]:
    if not depth:
        return data     # noqa
    if not iterable(data) or not data:
        return {key: [] for key in keys}
    result = {}
    for d in data:
        if not isinstance(d, dict):
            continue
        for k, v in d.items():
            if depth > 1:
                if multi(v) and v and isinstance(v[0], dict):
                    v = convert_data_frame(v, align=align, depth=depth - 1)
            if k not in result:
                result[k] = [v]
            else:
                result[k].append(v)
    if align:
        for key in list(result.keys()):
            if len(result[key]) != len(data):
                result.pop(key)
    return result


def gen_key(digit=64, alnum=False, lower=False, excludes: List[str] = ('$', '\\')) -> str:
    import secrets
    sample = string.digits
    if alnum:
        sample += string.ascii_lowercase if lower else string.ascii_letters
    else:
        sample = string.printable[:94]
    for ex in excludes:
        sample = sample.replace(ex, '')
    while len(sample) < digit:
        sample += sample
    return ''.join(secrets.choice(sample) for i in range(digit))    # noqa
    # return ''.join(random.sample(sample, digit))
