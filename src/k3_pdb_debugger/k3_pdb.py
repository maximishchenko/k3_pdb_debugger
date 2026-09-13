"""Консольный `pdb` для К3-Мебель с изолированным окном отладчика.

Модуль открывает отдельное консольное окно Windows и перенаправляет в
него `stdin`/`stdout`/`stderr` на время интерактивной сессии `pdb`,
не затрагивая собственные потоки ввода-вывода процесса `mebel.exe`.
Команды `q`/`quit`, `c`/`continue` и Ctrl+C корректно завершают
сессию отладчика и закрывают консольное окно, не завершая при этом
процесс К3-Мебель. `q`/Ctrl+C, как и в обычном `pdb`, прерывают
выполнение текущей операции через `bdb.BdbQuit`, но трейсбек этого
исключения в консоли К3-Мебель заменяется коротким сообщением.


Для подключения текущего модуля к глобальному вызову breakpoint (начиная
с версии Python 3.7) возможно использовать 2 способа:
- Установить значение переменной окружения PYTHONBREAKPOINT

```
set PYTHONBREAKPOINT=k3_pdb.set_trace
```

> При этом модуль k3_pdb.py должен находиться в области видимости sys.path

- Перехватить вызов sys.breakpointhook глобально

```
import sys
import k3_pdb

sys.breakpointhook = k3_pdb.set_trace
```

Пример использования:

```
from __future__ import annotations

import sys

import k3_pdb

sys.breakpointhook = k3_pdb.set_trace

def function(a: int | float, b: int | float) -> int | float:
    ab = a ** b
    string = 'example'
    print(string)
    breakpoint()
    ab = ab / 10
    return ab

function(2, 4)
```

`k3_pdb.set_trace` можно также использовать как декоратор с
именованным аргументом `enable`: если `enable` равен `True`, сессия
`pdb` запускается сразу при входе в декорируемую функцию; если
`False` — функция вызывается как обычно, без отладки:

```
@k3_pdb.set_trace(enable=True)  # отладка запускается
def function(a: int | float, b: int | float) -> int | float:
    ...

@k3_pdb.set_trace(enable=False)  # отладка не запускается
def function(a: int | float, b: int | float) -> int | float:
    ...
```
"""

from __future__ import annotations

import bdb
import functools
import sys
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    TypeVar,
    cast,
)

if TYPE_CHECKING:
    from .debugger import K3Debugger

_QUIT_MESSAGE = "Выход из режима отладки"

_F = TypeVar("_F", bound=Callable[..., Any])


class BdbQuitExceptHook:
    """Заменяет трейсбек `BdbQuit` коротким сообщением о выходе.

    `q`/Ctrl+C прерывают выполнение вызывающего кода через
    `bdb.BdbQuit`, чтобы корректно остановить текущую операцию К3 —
    как это делает обычный `pdb`. Но необработанный `BdbQuit`,
    дойдя до консоли К3-Мебель, выглядит как ошибка скрипта.
    Здесь трейсбек заменяется коротким сообщением, а прочие
    исключения обрабатываются исходным обработчиком без изменений.
    """

    def __init__(self) -> None:
        """Запомнить исходный `sys.excepthook`, до какой-либо подмены."""
        self._original = sys.excepthook
        self._installed = False

    def ensure_installed(self) -> None:
        """Один раз подменить `sys.excepthook` собой."""
        if self._installed:
            return

        sys.excepthook = self
        self._installed = True

    def __call__(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: TracebackType | None,
    ) -> None:
        """Перехватить `BdbQuit`, прочие исключения передать дальше."""
        if issubclass(exc_type, bdb.BdbQuit):
            print(_QUIT_MESSAGE)
            return
        self._original(exc_type, exc_value, exc_tb)


class ConditionalTrace:
    """Декоратор, запускающий сессию `pdb` при входе в функцию.

    Возвращается методом `K3Debugger.set_trace`, вызванным с
    именованным аргументом `enable` (`k3_pdb.set_trace(enable=...)`).
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
