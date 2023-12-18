from .base import Meta, Util
from .constant import Logic
from . import exceptions as exc
from typing import Dict, Any, List, Optional, Union


__all__ = ['LogicUtil']


class LogicUtil(Util, metaclass=Meta):
    XOR_ERROR_CLS = ValueError
    NOT_ERROR_CLS = ValueError

    def __init__(self, params: Dict[str, Any] = None):
        super().__init__(params)
        self._conditions: List[Union[LogicUtil, Any]] = []
        self._operator: Optional[str] = None
        # self._call = self.__call__
        # self.__call__ = self.__class__._apply_logic

    def apply(self, *args, **kwargs):
        raise NotImplementedError

    @property
    def _negate(self):
        return self._operator == Logic.NOT

    @property
    def _logic_applied(self):
        return bool(self._operator and self._conditions)

    def __hash__(self):
        return hash(repr(self))

    def apply_logic(self, *args, **kwargs):
        result = None
        errors = []
        if not self._logic_applied:
            try:
                result = self.apply(*args, **kwargs)
            except Exception as e:
                errors.append(e)
        else:
            if self._operator == Logic.OR:
                for con in self._conditions:
                    try:
                        result = con(*args, **kwargs)
                    except Exception as e:
                        errors.append(e)
                    else:
                        errors = []  # one condition is satisfied in OR
                        break
            elif self._operator == Logic.AND:
                for con in self._conditions:
                    try:
                        result = con(*args, **kwargs)
                    except Exception as e:
                        errors.append(e)
                        break
            elif self._operator == Logic.XOR:
                xor = None
                for con in self._conditions:
                    try:
                        result = con(*args, **kwargs)
                        if xor is None:
                            xor = con
                        else:
                            errors.append(self.XOR_ERROR_CLS(
                                f'More than 1 conditions ({xor}, {con}) is True in XOR conditions'))
                            xor = None
                            break
                    except Exception as e:
                        errors.append(e)
                if xor is not None:
                    # only one condition is satisfied in XOR
                    errors = []

            elif self._operator == Logic.NOT:
                try:
                    con = self._conditions[0]
                    result = con(*args, **kwargs)
                    errors.append(self.XOR_ERROR_CLS(f'Negate condition: {con} is violated'))
                except Exception as e:
                    # use error as result
                    result = self._get_error_result(e, *args, **kwargs)

        if errors:  # apply negate
            from .error import Error
            err = exc.CombinedError(*errors) if len(errors) > 1 else errors[0]
            raise Error(err).throw()
        return result

    def __call__(self, *args, **kwargs):
        return self.apply_logic(*args, **kwargs)

    def _get_error_result(self, err, *args, **kwargs):  # noqa
        return err

    def _combine(self, other, operator):
        name = self.__class__.__name__
        assert isinstance(other, self.__class__), \
            f"{name} instance must combine with other {name} instance, got {other}"
        util = self.__class__()
        util._operator = operator
        if self._operator == operator:
            util._conditions += self._conditions
        else:
            util._conditions.append(self)
        if other._operator == operator:
            util._conditions += other._conditions
        else:
            util._conditions.append(other)
        return util

    def _repr(self, params: List[str] = None, excludes: List[str] = None):
        if self._logic_applied:
            return self._operator.join([(f'({str(c)})' if c._logic_applied else str(c)) for c in self._conditions])
        return f'{Logic.NOT if self._negate else ""}{super()._repr(params=params, excludes=excludes)}'

    def __copy__(self):
        util = super(LogicUtil, self).__copy__()
        if self._operator:
            util._operator = self._operator
        if self._conditions:
            util._conditions = self._copy(self._conditions)
        return util

    def __eq__(self, other: 'LogicUtil'):
        if not isinstance(other, self.__class__):
            return False
        if self._operator:
            if self._operator != other._operator:
                return False
        if self._conditions:
            if self._conditions != other._conditions:
                return False
        return super(LogicUtil, self).__eq__(other)

    def __or__(self, other: 'LogicUtil'):
        return self._combine(other, Logic.OR)

    def __xor__(self, other: 'LogicUtil'):
        return self._combine(other, Logic.XOR)

    def __and__(self, other: 'LogicUtil'):
        return self._combine(other, Logic.AND)

    def __invert__(self):
        util = self.__copy__()
        util._conditions = [self]
        util._operator = Logic.NOT
        return util
