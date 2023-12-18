import os
import socket
import re
from datetime import datetime
from typing import Optional, List, Union, Tuple, Dict
from .. import constant
from ipaddress import ip_address, ip_network
posix_os = os.name == 'posix'

__all__ = [
    'dir_getsize', 'file_num',
    'get_ip',
    'path_merge',
    'load_ini', 'search_file',
    'clear', 'kill',
    'write_config', 'path_join',
    'running',
    'posix_os',
    'port_using',
    'run',
    'get_real_file',
    'read_from_socket',
    'sys_user_exists', 'sys_user_add', 'find_port',
    'parse_socket',
    'get_processes',
    'get_code',
    'current_master',
    'get_system_fds',
    'read_from',
    'write_to',
    'get_server_ip',
    'get_real_ip',
    'remove_file',
    'get_max_socket_conn',
    'get_max_open_files',
    'ip_belong_networks',
    'get_system_open_files',
    'create_only_write',
    'get_recursive_dirs',
    'get_sys_net_connections_info',
]


def remove_file(file: str, ignore_not_found: bool = True):
    try:
        os.remove(file)
        return True
    except FileNotFoundError as e:
        if ignore_not_found:
            return False
        raise e
    except PermissionError as e:
        if not posix_os:
            raise e
        return not os.system(f'sudo rm {file}')


def write_to(file: str, content: str, mode: str = 'w', encoding=None):
    try:
        with open(file, mode, encoding=encoding) as f:
            f.write(content)
    except (PermissionError, FileNotFoundError) as e:
        if not posix_os:
            raise e
        note = '-a' if mode.startswith('a') else ''
        # use single quote here to apply $ escape
        os.system(f"echo \'{content}\' | sudo tee {note} {file} >> /dev/null")    # ignore file content output


def create_only_write(file: str, content: str, fail_silently: bool = False):
    import os
    import errno

    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY

    try:
        file_handle = os.open(file, flags)
    except OSError as e:
        if e.errno == errno.EEXIST:  # Failed as the file already exists.
            pass
        else:  # Something unexpected went wrong so reraise the exception.
            if not fail_silently:
                raise
    else:  # No exception, so the file must have been created successfully.
        with os.fdopen(file_handle, 'w') as file_obj:
            # Using `os.fdopen` converts the handle to an object that acts like a
            # regular Python file object, and the `with` context manager means the
            # file will be automatically closed when we're done with it.
            file_obj.write(content)


def read_from(file, mode: str = 'r') -> str:
    try:
        with open(file, mode, errors='ignore') as f:
            return f.read()
    except PermissionError:
        if posix_os:
            return os.popen(f'sudo cat {file}').read()
        return ''
    except FileNotFoundError:
        return ''


def get_system_fds():
    import psutil
    fds = 0
    if psutil.POSIX:
        for proc in psutil.process_iter():
            try:
                fds += proc.num_fds()
            except psutil.Error:
                continue
    return fds


def get_system_open_files():
    import psutil
    files = 0
    for proc in psutil.process_iter():
        try:
            files += len(proc.open_files())
        except psutil.Error:
            continue
    return files


def get_network_ip(ifname: str):
    import struct
    try:
        import fcntl
    except ModuleNotFoundError:
        return None
    if isinstance(ifname, str):
        ifname = ifname.encode()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        return socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915,  struct.pack('256s', ifname[:15]))[20:24])   # noqa
    except OSError:
        return None


def get_server_ip(private_only: bool = False) -> Optional[str]:
    ip = socket.gethostbyname(socket.gethostname())
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    ips = set()
    for i in range(0, 3):
        if_ip = get_network_ip(f'eth{i}')
        if if_ip:
            if not if_ip.startswith('127.'):
                ips.add(if_ip)
        else:
            break

    if ip:
        if ip.startswith('127.'):
            s.connect(('8.8.8.8', 53))
            ip = str(s.getsockname()[0])
            if ip:
                ips.add(ip)
            s.close()
        else:
            ips.add(ip)

    for ip in ips:
        try:
            addr = ip_address(ip)
            if addr.is_loopback:
                # ignore loopback addr
                continue
            if private_only and not addr.is_private:
                continue
            return ip
        except ValueError:
            continue
    return ips.pop() if ips else constant.LOCAL_IP


def ip_belong_networks(ip, networks: List[str]):
    if not networks or not ip:
        return True
    if isinstance(ip, str):
        ip = ip_address(ip)
    for addr in networks:
        try:
            if ip in ip_network(addr):
                return True
        except ValueError:
            continue
    return False


def file_num(path) -> int:
    num = 0
    for root, dirs, files in os.walk(path):
        num += len(files)
    return num


def dir_getsize(path):
    size = 0
    for root, dirs, files in os.walk(path):
        size += sum([os.path.getsize(os.path.join(root, name)) for name in files])
    return size


def get_real_file(path: str):
    try:
        real_path = os.readlink(path)
        if not os.path.exists(real_path):
            raise FileNotFoundError
    except (OSError, FileNotFoundError):
        real_path = path
    if not os.path.exists(real_path):
        raise FileNotFoundError(f'file: {repr(real_path)} not exists')
    return real_path


def load_ini(content: str, parse_key: bool = False) -> dict:
    ini = {}
    dic = {}
    for ln in content.splitlines():
        line = ln.replace(' ', '').replace('\t', '')
        if not line or not line.split():
            continue
        annotate = line.split()[0].startswith('#') or line.split()[0].startswith(';')
        if annotate:
            continue
        if re.fullmatch('\\[(.*?)\\]', line):
            key = line.strip('[]')
            ini[key] = dic = {}
        else:
            from utype import TypeTransformer
            key, val = line.split('=')
            if parse_key:
                key = key.replace('_', '-').lower()
            if val.isdigit():
                val = int(val)
            elif val in TypeTransformer.FALSE_VALUES:
                val = False
            dic[key] = val
    return ini or dic   # load no header conf file as well


def write_config(data: dict, path: str, append: bool = False, ini_syntax: bool = True) -> str:
    content = ''
    if ini_syntax:
        for key, val in data.items():
            content += f'[{key}]\n'
            assert type(val) == dict, TypeError(f"write ini failed, syntax error: {val} should be dict")
            for k, v in val.items():
                content += f'{k} = {v}\n'
            content += '\n'
    else:
        for k, v in data.items():
            content += f'{k} = {repr(v)}\n'
        content += '\n'

    write_to(path, content=content, mode='a' if append else 'w')
    return content


def path_join(base: str, path: str, *, dir: bool = False, create: bool = False, ignore: bool = False):
    if not path:
        return None
    if os.path.isabs(path):
        p = path
    else:
        p = path_merge(base, path)
    if not os.path.exists(p):
        if create:
            if dir:
                os.makedirs(p)
            else:
                write_to(p, content='')
        elif not ignore:
            raise OSError(f"path {p} not exists")
    return p


def search_file(filename, path=os.getcwd()):
    file = os.path.join(path, filename)
    while os.path.dirname(path) != path:
        if os.path.exists(file):
            return file
        path = os.path.dirname(path)
        file = os.path.join(path, filename)
    return None


def clear(filepath):
    files = os.listdir(filepath)
    for fd in files:
        cur_path = os.path.join(filepath, fd)
        if os.path.isdir(cur_path):
            if fd == "__pycache__":
                import shutil
                shutil.rmtree(cur_path)
            else:
                clear(cur_path)


def run(cmd, *backup_commands):
    try:
        r = os.system(cmd)
        if r:
            for c in backup_commands:
                r = os.system(c)
                if not r:
                    return
            print(f'UtilMeta occur error, aborting..')
            exit(r)
    except KeyboardInterrupt:
        print('aborting..')
        exit(0)
    except Exception as e:
        print(f'UtilMeta occur error: {e}, aborting..')
        exit(1)


def current_master():
    import psutil
    return bool(psutil.Process(os.getpid()).children())


def get_processes(name, contains: str = None):
    import psutil
    assert name, name
    ls = []
    for p in psutil.process_iter():
        name_, exe, cmdline = "", "", []
        try:
            name_ = p.name()
            cmdline = p.cmdline()
            exe = p.exe()
        except (psutil.AccessDenied, psutil.ZombieProcess):
            pass
        except psutil.NoSuchProcess:
            continue
        if name == name_ or os.path.basename(exe) == name:
            if contains and not any([contains in cmd for cmd in cmdline]):
                continue
            ls.append(p)
    return ls


def kill(name, contains: str = None):
    import psutil
    killed = 0
    for p in get_processes(name=name, contains=contains):
        try:
            p.kill()
            killed += 1
        except (OSError, psutil.Error):
            continue
    return killed


def port_using(port: int):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        return not bool(s.connect_ex((constant.LOCAL_IP, port)))
    except (OSError, *constant.COMMON_ERRORS):
        return True


def find_port():
    ports = []

    def find(start: int = 8000, end: int = 10000):
        for p in range(start, end):
            if port_using(p) or p in ports:
                continue
            ports.append(p)
            return p
    return find


def get_max_socket_conn():
    if not posix_os:
        return None
    r = os.popen('cat /proc/sys/net/core/somaxconn').read().strip('\n')
    if not r:
        return None
    return int(r)


def get_max_open_files():
    if not posix_os:
        return None
    r = os.popen('ulimit -n').read().strip('\n')
    if not r:
        return None
    return int(r)


def running(pid):
    import psutil
    try:
        return psutil.Process(pid).is_running()
    except psutil.Error:
        return False


def parse_socket(sock: str, valid_path: bool = False):
    file = False
    if callable(sock):
        sock = sock()
    assert sock, f'Invalid socket: {sock}'
    if isinstance(sock, int) or isinstance(sock, str) and sock.isdigit():
        try:
            sock = int(sock)
            assert 1000 < sock < 65536
        except (TypeError, ValueError, AssertionError) as e:
            raise ValueError(f'socket must be a valid .sock file path or a int port '
                             f'in (1000, 65536), got {sock} with error {e}')
        else:
            sock = f'127.0.0.1:{sock}'
    elif valid_path:
        if os.path.exists(sock):
            file = True
    else:
        file = True
    return sock, file


def read_from_socket(value: Union[str, int], buf: int = 1024 * 4) -> bytes:
    sock, file = parse_socket(value, valid_path=True)
    if file:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(sock)
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        host, port = sock.split(':')
        s.connect((host, int(port)))
    data = b''
    while 1:
        d = s.recv(buf)
        data += d
        if len(d) < buf:
            break
    s.close()
    return data


def sys_user_exists(name: str, group: bool = False):
    if name is None:
        return False
    # name can be a user name (like root) or user id (like 0)
    if not posix_os:
        return False
    if group:
        return bool(os.popen(f'grep "{name}" /etc/group').read())
    else:
        return bool(os.popen(f'grep "{name}" /etc/passwd').read())


def sys_user_add(name: str, home: str = None, group: str = None, login: bool = True, add_group: bool = False):
    if not posix_os:
        return
    if not name:
        return
    if add_group:
        os.system(f'groupadd {name}')
        return
    items = []
    if not login:
        items.append('-s /bin/false')
    if home:
        items.append(f'-d {home}')
    if group:
        items.append(f'-g {group}')
    append_str = ' '.join(items)
    os.system(f'useradd {append_str} {name}')


def get_code(f) -> str:
    # not used in current version
    code = getattr(f, constant.Attr.CODE, None)
    if not code:
        return ''
    fl = code.co_firstlineno
    file = code.co_filename
    content = read_from(file)
    ft = 0
    el = fl
    for i, line in enumerate(content.splitlines()[fl:]):
        tabs = line.count(' ' * 4)
        if not i:
            ft = tabs
            continue
        if tabs <= ft:
            el = fl + i
            break
    return '\n'.join(content.splitlines()[fl:el])


def get_sys_net_connections_info() -> Tuple[int, int, Dict[str, int]]:    # (total, active)
    import psutil
    info = {}
    conns = []
    try:
        conns = psutil.net_connections()
    except psutil.AccessDenied:
        # in MacOS
        iterator = psutil.process_iter()
        while True:
            try:
                proc = next(iterator)
                conns.extend(proc.connections())
            except psutil.Error:
                continue
            except StopIteration:
                break
    except psutil.Error as e:
        import warnings
        warnings.warn(f'retrieve net connections failed with error: {e}')
        return 0, 0, {}
    total = len(conns)
    active = 0
    for c in conns:
        if c.status in info:
            info[c.status] += 1
        else:
            info[c.status] = 1
        if c.status not in constant.IDLE_TCP_STATUSES:
            active += 1
    return total, active, info


def path_merge(base: str, path: str):
    """
        the base param is a absolute dir (usually the os.getcwd())
        path can be regular path like dir1/file2
        or the double-dotted path ../../file1
        in every case the base and path will merge to a absolute new path
    """
    path = path or ''
    if path.startswith('./'):
        path = path.strip('./')

    if path.startswith('/') or path.startswith('~'):
        return path

    if not path:
        return base or ''

    if '..' in path:
        divider = os.sep
        dirs = path.split(divider)
        backs = dirs.count('..')
        while backs:
            base = os.path.dirname(base)
            backs -= 1
        path = divider.join([d for d in dirs if d != '..'])
    return os.path.join(base, path).replace('/', os.sep).replace('\\', os.sep).rstrip(os.sep)


def get_recursive_dirs(path, exclude_suffixes: List[str] = None, include_suffixes: List[str] = None,
                       include_path: bool = False, file_stats: bool = False, dir_stats: bool = False,
                       exclude_seg: bool = False, exclude_dot: bool = False):
    try:
        ab_path, dirs, files = next(os.walk(path))
    except (FileNotFoundError, StopIteration):
        return []

    def _trans_stats(p):
        try:
            dt = os.stat(p)
            return dict(
                size=dt.st_size,
                uid=dt.st_uid,
                gid=dt.st_gid,
                last_access=datetime.fromtimestamp(dt.st_atime),
                last_modified=datetime.fromtimestamp(dt.st_mtime),
                created_time=datetime.fromtimestamp(dt.st_ctime),
            )
        except (FileNotFoundError, PermissionError):
            return {}

    result = []
    for dir in dirs:
        if exclude_seg and dir.startswith(constant.SEG):
            continue
        if exclude_dot and dir.startswith('.'):
            continue
        dir_path = os.path.join(path, dir)
        values = get_recursive_dirs(
            dir_path,
            include_path=include_path,
            file_stats=file_stats,
            dir_stats=dir_stats,
            exclude_seg=exclude_seg,
            exclude_dot=exclude_dot,
            include_suffixes=include_suffixes,
            exclude_suffixes=exclude_suffixes
        )
        val = dict(
            name=dir,
            children=values
        )
        if include_path:
            val.update(path=dir_path)
        if dir_stats:
            val.update(_trans_stats(dir_path))
        result.append(val)
    for file in files:
        if include_suffixes and not any([file.endswith(f'.{s}') for s in include_suffixes]):
            continue
        if exclude_suffixes and any([file.endswith(f'.{s}') for s in exclude_suffixes]):
            pass
        val = dict(
            name=file,
        )
        f_path = os.path.join(path, file)
        if include_path:
            val.update(path=f_path)
        if file_stats:
            val.update(_trans_stats(f_path))
        result.append(val)
    return result


def get_ip(host: str, ip_only: bool = False) -> Optional[str]:
    ip_reg = re.compile(f'^{constant.Reg.IP}')
    match = ip_reg.match(host)
    if match:
        return match.group()
    from urllib.parse import urlparse, ParseResult
    res: ParseResult = urlparse(host)
    match = ip_reg.match(res.netloc)
    if match:
        return match.group()
    if ip_only:
        return None
    from .web import get_hostname
    try:
        return socket.gethostbyname(get_hostname(host))
    except (socket.error, OSError):
        return constant.LOCAL_IP


def get_real_ip(ip: str):
    from .web import localhost
    if localhost(ip):
        return get_server_ip()
    return get_ip(ip)
