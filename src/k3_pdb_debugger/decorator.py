"""Декоратор для запуска отладчика."""

from __future__ import annotations

import functools
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    TypeVar,
    cast,
)

if TYPE_CHECKING:  # pragma: no cover
    from .debugger import K3Debugger

_F = TypeVar("_F", bound=Callable[..., Any])


class ConditionalTrace:
    """Декоратор, запускающий сессию `pdb` при входе в функцию.

    Возвращается методом `K3Debugger.set_trace`, вызванным с
    именованным аргументом `enable` (`set_trace(enable=...)`).
    Если `enable` равен `False`, декорируемая функция вызывается без
    каких-либо изменений — консоль отладчика не открывается.
    """

    def __init__(self, debugger: K3Debugger, enable: bool) -> None:
        """Запомнить отладчик и признак включения точки останова."""
        self._debugger = debugger
        self._enable = enable

    def __call__(self, func: _F) -> _F:
        """Обернуть `func`, если отладка включена, иначе вернуть как есть."""
        if not self._enable:
            return func

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            self._debugger.set_trace()
            return func(*args, **kwargs)

        return cast(_F, wrapper)
