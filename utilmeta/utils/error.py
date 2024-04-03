import traceback
from typing import Type, Dict, Callable, Optional, List
from . import Attr, SEG, readable
import sys
import inspect
import time


class Error:
    def __init__(self, e: Exception = None):
        if isinstance(e, Exception):
            self.exc = e
            self.type = e.__class__
            self.exc_traceback = e.__traceback__
        elif isinstance(e, Error):
            self.exc = e.exc
            self.type = e.type
            self.exc_traceback = e.exc_traceback
        else:
            exc_type, exc_instance, exc_traceback = sys.exc_info()
            self.exc = exc_instance
            self.type = exc_type
            self.exc_traceback = exc_traceback

        self.locals = {}
        self.current_traceback = ''
        self.traceback = ''
        self.variable_info = ''
        self.full_info = ''
        self.ts = time.time()

    def setup(self):
        if self.current_traceback:
            return
        # FIXME: lots of performance cost in this function
        self.current_traceback = ''.join(traceback.format_tb(self.exc_traceback))
        causes = self.get_causes()
        if len(causes) > 1:
            traces = []
            local_vars = {}
            for cause in causes:
                if cause is self:
                    traces.append(self.current_traceback)
                else:
                    cause.setup()
                    traces.append(cause.current_traceback)
                local_vars.update(cause.locals)
            self.traceback = '# this error is caused by:\n'.join(traces)
            self.locals = local_vars
        else:
            self.traceback = self.current_traceback
            try:
                self.locals = inspect.trace()[-1][0].f_locals
                # self.locals: Dict[str, Any] = Util.clean_kwargs(inspect.trace()[-1][0].f_locals, display=True)
            except IndexError:
                self.locals = {}

        variables = []
        if self.locals:
            variables.append('Exception Local Variables:')
        for key, val in self.locals.items():
            if key.startswith(SEG) and key.endswith(SEG):
                continue
            try:
                variables.append(f'{key} = {readable(val, max_length=100)}')
            except Exception as e:
                print(f'Variable <{key}> serialize error: {e}')
        self.variable_info = '\n'.join(variables)
        self.full_info = '\n'.join([self.message, *variables])
        # self.record_disabled = getattr(self.exc, 'record_disabled', False)

    def __str__(self):
        return f'<{self.type.__name__}: {str(self.exc)}>'

    @property
    def exception(self):
        return self.exc

    @property
    def message(self) -> str:
        return '{0}{1}: {2}'.format(
            self.traceback,
            self.type.__name__,
            self.exc
        )

    @property
    def root_cause(self) -> 'Error':
        return self.get_causes()[0]

    def get_causes(self) -> List['Error']:
        # causes = getattr(self.exc, Attr.CAUSES, [])
        # cause_reasons = [str(c.current_traceback) for c in causes]
        # if self.current_traceback in cause_reasons:
        #     return causes
        return [self, *getattr(self.exc, Attr.CAUSES, [])]

    # @property
    # def target(self) -> 'Error':
    #     errors = []
    #     target = None
    #     for e in [*self.causes, self]:
    #         if str(e) in errors:
    #             continue
    #         errors.append(str(e))
    #         target = e
    #     return target or self

    @property
    def status(self) -> int:
        status = getattr(self.exc, 'status', None)
        if isinstance(status, int) and 100 <= status <= 600:
            return status
        return 500

    @property
    def result(self):
        return getattr(self.exc, 'result', None)

    @property
    def state(self):
        return getattr(self.exc, 'state', None)

    @property
    def headers(self):
        return getattr(self.exc, 'headers', None)

    def log(self, console: bool = False) -> int:
        if not self.full_info:
            self.setup()
        # from .log import Logger
        # if isinstance(logger, Logger):
        #     logger.resolve(brief=str(self), msg=self.full_info, status=self.status)
        if console:
            print(self.full_info)
        return self.status

    @property
    def cause_func(self):
        stk = traceback.extract_tb(self.exc_traceback, 1)
        return stk[0][2]

    def throw(self, type=None, prepend: str = '', **kwargs):
        if not (inspect.isclass(type) and issubclass(type, Exception)):
            type = None
        type = type or self.type
        if prepend or not isinstance(self.exc, type):
            e = type(f'{prepend}{self.exc}', **kwargs)  # noqa
            setattr(e, Attr.CAUSES, self.get_causes())
        else:
            e = self.exc
        # it need the throw caller to raise the error like: raise Error().throw()
        # cause in that way can track the original variables
        return e

    def get_hook(self, hooks: Dict[Type[Exception], Callable], exact: bool = False) -> Optional[Callable]:
        if not hooks:
            return None

        def _get(_e):
            for et, func in hooks.items():
                if et is Exception:
                    continue
                if exact:
                    if _e == et:
                        return func
                else:
                    if isinstance(_e, et):
                        return func

        hook = _get(self.exc)
        if hook or exact:
            return hook

        # exact does not take Exception as the finally fallback
        default = hooks.get(Exception)
        # if self.combined:
        #     values = set()
        #     for err in self:
        #         _hook = _get(err)
        #         if _hook:
        #             values.add(_hook)
        #     if len(values) == 1:
        #         return values.pop()

        return default
