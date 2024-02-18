import platform
import psutil
import os
import time
from utilmeta.utils import get_max_open_files, get_max_socket_conn


def get_server_statics():
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(os.getcwd())

    devices = {}
    for device in psutil.disk_partitions():
        if 'loop' in device.device:
            continue
        try:
            disk_usage = psutil.disk_usage(device.mountpoint)
        except PermissionError:
            continue
        devices[device.device] = dict(
            mountpoint=device.mountpoint,
            fstype=device.fstype,
            opts=device.opts,
            total=disk_usage.total,
            used=disk_usage.used
        )

    return dict(
        cpu_num=os.cpu_count(),
        memory_total=mem.total,
        disk_total=disk.total,
        utcoffset=-time.timezone,
        hostname=platform.node(),
        system=str(platform.system()).lower(),
        devices=devices,
        max_open_files=get_max_open_files(),
        max_socket_conn=get_max_socket_conn(),
        platform=dict(
            platform=platform.platform(),
            version=platform.version(),
            release=platform.release(),
            machine=platform.machine(),
            processor=platform.processor(),
            bits=platform.architecture()[0]
        )
    )
