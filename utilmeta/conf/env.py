from utype import Schema, Options
from typing import Union, Mapping
import os
import json


class Env(Schema):
    __options__ = Options(case_insensitive=True)

    def __init__(self,
                 data: Union[Mapping, dict] = None,
                 sys_env: Union[bool, str] = None,
                 ref: str = None,
                 file: str = None):
        self._data = data or {}
        self._sys_env = bool(sys_env)
        self._sys_env_prefix = sys_env if isinstance(sys_env, str) else ''
        self._ref = ref
        self._file = file
        for items in (
            self._load_from_ref(),
            self._load_from_file(),
            self._load_from_sys_env()
        ):
            if items:
                self._data.update(items)
        super().__init__(**self._data)

    def _load_from_sys_env(self) -> Mapping:
        if not self._sys_env:
            return {}
        data = {}
        for key, value in os.environ.items():
            if key.lower().startswith(self._sys_env_prefix.lower()):
                data[key[len(self._sys_env_prefix):]] = value
        return data

    def _load_from_file(self) -> Mapping:
        if not self._file:
            return {}
        if not os.path.exists(self._file):
            rel_file = os.path.join(os.getcwd(), self._file)
            if not os.path.exists(rel_file):
                raise FileNotFoundError(f'{self.__class__}: file: {repr(self._file)} not exists')
            else:
                self._file = rel_file

        if self._file.endswith('.json'):
            return json.load(open(self._file, 'r'))

        if self._file.endswith('.yml') or self._file.endswith('.yaml'):
            from utilmeta.utils import requires
            requires(yaml='pyyaml')
            import yaml
            return yaml.safe_load(open(self._file, 'r'))

        content = open(self._file, 'r').read()
        data = {}
        for line in content.splitlines():
            if not line.strip():
                # empty line
                continue
            try:
                key, value = line.split('=')
            except ValueError as e:
                raise ValueError(f'{self.__class__}: file: {repr(self._file)} invalid line: {repr(line)}, '
                                 f'should be <KEY>=<VALUE>') from e
            key = str(key).strip()
            value = str(value).strip()
            if key:
                data[key] = value
        return data

    def _load_from_ref(self) -> Mapping:
        if not self._ref:
            return {}
        from utilmeta.utils import import_obj
        obj = import_obj(self._ref)
        if isinstance(obj, Mapping):
            return obj
        if hasattr(obj, '__dict__') and isinstance(obj.__dict__, Mapping):
            return obj.__dict__
        raise TypeError(f'{self.__class__}: invalid ref: {repr(self._ref)}, dict or class expetect, got {obj}')
