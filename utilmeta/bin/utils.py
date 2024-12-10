from utilmeta.utils import search_file, load_ini, read_from, write_config, pop
import os


def update_meta_ini_file(path: str = None, /, **settings):
    if not settings:
        return
    cwd = path or os.getcwd()
    ini_path = search_file("utilmeta.ini", path=cwd) or search_file(
        "meta.ini", path=cwd
    )
    if not ini_path:
        return
    config = load_ini(read_from(ini_path), parse_key=True)
    service_config = dict(config.get("utilmeta") or config.get("service") or {})
    for key, val in settings.items():
        if val is None:
            pop(service_config, key)
        else:
            service_config[key] = val
    write_config({"utilmeta": service_config}, ini_path)
