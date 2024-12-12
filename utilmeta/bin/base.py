from typing import Type, Callable, Dict, Iterable, List, Union
import utype
from utype.utils.exceptions import AbsenceError
from utype import Field, parse, Options
from utype.utils.compat import Literal
from utype.utils.datastructures import unprovided
from utype.parser.rule import ConstraintMode
from utilmeta.utils import get_doc, Error
from .constant import RED
import inspect
from functools import partial


__all__ = ["command", "Arg", "BaseCommand"]


def command(name: str = None, *aliases, options: Options = None):
    parser = parse(ignore_result=True, options=options)
    if callable(name):
        name = parser(name)
        name.__command__ = name.__name__
        name.__aliases__ = []
        return name

    def wrapper(f):
        f = parser(f)
        f.__command__ = f.__name__ if name is None else name
        f.__aliases__ = aliases
        return f

    return wrapper


class Arg(Field):
    def __init__(
        self,
        alias: str = None,
        alias_from: Union[str, List[str], Callable, List[Callable]] = None,
        *,
        required: bool = False,
        default=None,
        default_factory: Callable = None,
        case_insensitive: bool = None,
        mode: str = None,
        deprecated: Union[bool, str] = False,
        discriminator=None,  # discriminate the schema union by it's field
        no_input: Union[bool, str, Callable] = False,
        on_error: Literal["exclude", "preserve", "throw"] = None,  # follow the options
        dependencies: Union[list, str, property] = None,
        # --- ANNOTATES ---
        title: str = None,
        description: str = None,
        example=unprovided,
        # --- CONSTRAINTS ---
        const=unprovided,
        enum: Iterable = None,
        gt=None,
        ge=None,
        lt=None,
        le=None,
        regex: str = None,
        length: Union[int, ConstraintMode] = None,
        max_length: Union[int, ConstraintMode] = None,
        min_length: int = None,
        # number
        max_digits: Union[int, ConstraintMode] = None,
        decimal_places: Union[int, ConstraintMode] = None,
        round: int = None,
        multiple_of: Union[int, ConstraintMode] = None,
        # array
        contains: type = None,
        max_contains: int = None,
        min_contains: int = None,
        unique_items: Union[bool, ConstraintMode] = None,
    ):
        if required:
            default = default_factory = unprovided
        kwargs = dict(locals())
        kwargs.pop("self")
        kwargs.pop("__class__")
        super().__init__(**kwargs)


class BaseCommand:
    _commands: Dict[str, Union[Type["BaseCommand"], Callable]] = {}
    _documents: Dict[str, str] = {}
    _aliases: Dict[str, str] = {}

    fallback: Callable = None
    name: str = None
    script_name: str = None

    class PartialCommand:
        def __init__(self, func: Callable, cls):
            self.func = func
            self.cls = cls

        def __call__(self, *argv: str, cwd: str) -> Callable:
            return partial(self.func, self.cls(*argv, cwd=cwd))

    def __init_subclass__(cls, **kwargs):
        commands = {}
        documents = {}
        aliases = {}

        for base in reversed(cls.__bases__):  # mro
            if issubclass(base, BaseCommand):
                commands.update(base._commands)
                documents.update(base._documents)
                aliases.update(base._aliases)

        for name, cmd in cls.__annotations__.items():
            if isinstance(cmd, type) and issubclass(cmd, BaseCommand):
                commands[name] = cmd
                cmd_documents = cmd._documents
                documents[name] = get_doc(cmd) or cmd_documents.get("")

        for name, func in cls.__dict__.items():
            name: str
            if name in commands:
                continue
            if name.startswith("_"):
                continue
            cls_func = False
            if isinstance(func, classmethod):
                func = func.__func__
                cls_func = True
                # func.__classmethod__ = True
            if not inspect.isfunction(func):
                continue
            command_name = getattr(func, "__command__", None)
            if command_name is None:
                continue
            command_aliases = getattr(func, "__aliases__", [])
            documents[command_name] = get_doc(func)
            # if cls_func:
            #     func = partial(func, cls)
            # else:
            #     func = cls.PartialCommand(func, cls)
            commands[command_name] = (cls, func, cls_func)
            if command_aliases:
                for alias in command_aliases:
                    aliases[alias] = name

        cls._commands = commands
        cls._documents = documents
        cls._aliases = aliases

    def __init__(self, *argv: str, cwd: str):
        self.argv = argv
        self.cwd = cwd
        if argv:
            self.arg_name, *self.args = argv
            # like meta --ini ...
            if self.arg_name.startswith("--"):
                self.arg_name = ""
                self.args = argv
        else:
            self.arg_name = ""
            self.args = []

    def get_command_cls(self, name: str) -> Union[Type["BaseCommand"], Callable]:
        alias = self._aliases.get(name, name)
        return self._commands.get(alias)

    def command_not_found(self):
        print(RED % f'{self.script_name or "meta"}: command not found: {self.arg_name}')
        exit(1)

    def __call__(self, **kwargs):
        cmd_cls = self.get_command_cls(self.arg_name)

        # if not cmd_cls:
        #     root_cmd = self.get_command_cls('')
        #     if root_cmd:
        #         # the arg_name is actually the calling args for root cmd
        #         cmd_cls = root_cmd
        #         self.args = self.argv

        if not cmd_cls:
            fb = self.fallback
            if isinstance(fb, self.PartialCommand):
                fb = fb(*self.argv, cwd=self.cwd)
            if fb:
                fb()
                return
            elif self.name:
                # subclasses
                root_cmd = self.get_command_cls("")
                if root_cmd:
                    # the arg_name is actually the calling args for root cmd
                    cmd_cls = root_cmd
                    self.args = self.argv
                else:
                    raise ValueError(
                        f'{self.script_name or "meta"} {self.name or ""}: Invalid command: {self.argv}'
                    )
            else:
                self.command_not_found()

        if isinstance(cmd_cls, tuple):
            cls, func, cls_func = cmd_cls
            if issubclass(self.__class__, cls):
                cls = self.__class__
            if cls_func:
                func = partial(func, cls)
            else:
                func = cls.PartialCommand(func, cls)
            cmd_cls = func

        if isinstance(cmd_cls, type):
            cmd = cmd_cls(*self.argv, cwd=self.cwd)
            return cmd()
        else:
            if isinstance(cmd_cls, self.PartialCommand):
                cmd = cmd_cls(*self.argv, cwd=self.cwd)
            else:
                cmd = cmd_cls

            args = []
            for arg in self.args:
                arg = str(arg)
                if arg.startswith("--"):
                    if "=" in arg:
                        key, *values = arg.split("=")
                        val = "=".join(values)
                        kwargs[key] = val  # = kwargs[str(key).strip('--')]
                    else:
                        kwargs[arg] = True  # = kwargs[str(arg).strip('--')]
                elif arg.startswith("-"):
                    kwargs[arg] = True  # kwargs[arg.strip('-')] =
                else:
                    args.append(arg)
            try:
                return cmd(*args, **kwargs)
            except utype.exc.ParseError as e:
                self.handle_parse_error(e)

    def handle_parse_error(self, e: Exception):
        if isinstance(e, AbsenceError):
            message = f"required command argument: {repr(e.item)} is absence"
        else:
            message = str(e)
        error = Error(e)
        error.setup()
        print(error.full_info)
        print(
            RED
            % f'{self.script_name or "meta"} {self.name or ""}: command [{self.arg_name}] failed: {message}'
        )
        exit(1)

    @classmethod
    def mount(cls, cmd_cls: Type["BaseCommand"], name: str = "", *aliases: str):
        if not issubclass(cmd_cls, BaseCommand):
            raise TypeError(
                f"Invalid command class: {cmd_cls}, should be BaseCommand subclass"
            )
        for alias in aliases:
            cls._aliases[alias] = name
        cls._commands[name] = cmd_cls

    @classmethod
    def merge(cls, cmd_cls: Type["BaseCommand"]):
        if not issubclass(cmd_cls, BaseCommand):
            raise TypeError(
                f"Invalid command class: {cmd_cls}, should be BaseCommand subclass"
            )
        cls._commands.update(cmd_cls._commands)
        cls._aliases.update(cmd_cls._aliases)
        cls._documents.update(cmd_cls._documents)
        if not cls.fallback and cmd_cls.fallback:
            if inspect.ismethod(cmd_cls.fallback):
                cls.fallback = cmd_cls.fallback
            else:
                cls.fallback = cls.PartialCommand(cmd_cls.fallback, cls=cmd_cls)
