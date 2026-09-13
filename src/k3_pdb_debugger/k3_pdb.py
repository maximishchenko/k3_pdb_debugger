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

import _thread
import bdb
import ctypes
import functools
import pdb
import sys
from ctypes import wintypes
from types import TracebackType
from typing import (
    Any,
    Callable,
    TextIO,
    TypeVar,
    cast,
    overload,
)

kernel32: ctypes.WinDLL = ctypes.windll.kernel32

# Сигнатура обработчика для перехвата консольных событий Windows
# (см. SetConsoleCtrlHandler / HandlerRoutine в WinAPI).
PHANDLER_ROUTINE = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
CTRL_C_EVENT = 0

_QUIT_MESSAGE = "Выход из режима отладки"

_F = TypeVar("_F", bound=Callable[..., Any])


class _DebugConsole:
    """Изолированное консольное окно Windows для сессии `pdb`.

    Отвечает за создание и закрытие окна консоли, перенаправление
    `stdin`/`stdout`/`stderr` в него на время сессии отладчика и
    защиту процесса К3-Мебель от завершения по Ctrl+C.
    """

    def __init__(self) -> None:
        """Запомнить исходные потоки К3, до какой-либо подмены."""
        self._original_stdin: TextIO = sys.stdin
        self._original_stdout: TextIO = sys.stdout
        self._original_stderr: TextIO = sys.stderr

        self.stdin: TextIO | None = None  # noqa: UP045
        self.stdout: TextIO | None = None  # noqa: UP045

        self.active = False

        self._created = False
        # Ссылку на обработчик нужно хранить, иначе её удалит
        # Garbage Collector, и Windows будет вызывать освобождённую
        # функцию.
        self._ctrl_handler: Any | None = None  # noqa: UP045

    def enable(self) -> None:
        """Открыть консольное окно Windows, если оно ещё не открыто."""
        if kernel32.GetConsoleWindow():
            return

        if not kernel32.AllocConsole():
            raise ctypes.WinError()

        self._created = True

        self._ctrl_handler = PHANDLER_ROUTINE(self._on_ctrl_event)
        kernel32.SetConsoleCtrlHandler(self._ctrl_handler, True)

    def setup_streams(self) -> None:
        """Перенаправить `stdin`/`stdout`/`stderr` в консольное окно."""
        self.stdin = open("CONIN$")
        self.stdout = open("CONOUT$", "w", buffering=1)

        sys.stdin = self.stdin
        sys.stdout = self.stdout
        sys.stderr = self.stdout

    def detach(self) -> None:
        """Вернуть потоки К3 и закрыть консольное окно отладчика."""
        # Гарантированно снимаем хук трассировки перед закрытием потоков.
        sys.settrace(None)

        sys.stdin = self._original_stdin
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr

        if self.stdin is not None:
            try:
                self.stdin.close()
            except OSError:
                pass
            self.stdin = None

        if self.stdout is not None:
            try:
                self.stdout.close()
            except OSError:
                pass
            self.stdout = None

        if self._created:
            if self._ctrl_handler:
                kernel32.SetConsoleCtrlHandler(self._ctrl_handler, False)
                self._ctrl_handler = None

            kernel32.FreeConsole()
            self._created = False

    def release(self) -> None:
        """Пометить сессию отладчика завершённой и закрыть консоль."""
        self.active = False
        self.detach()

    def _on_ctrl_event(self, ctrl_type: int) -> bool:
        """Обработать событие консоли Windows (см. HandlerRoutine WinAPI).

        Обработчик вызывается Windows в отдельном потоке и должен
        всегда возвращать `True`: К3-Мебель встраивает Python без
        установки его штатных обработчиков сигналов, поэтому при
        возврате `False` и отсутствии другого обработчика, вернувшего
        `True`, Windows применяет действие по умолчанию для
        `CTRL_C_EVENT` — завершает весь процесс К3-Мебель, а не
        только консоль отладчика. Пока сессия `pdb` активна,
        `KeyboardInterrupt` в основной поток доставляется явно через
        `_thread.interrupt_main()`.
        """
        if ctrl_type == CTRL_C_EVENT:
            if self.active:
                _thread.interrupt_main()
            return True
        return False


class _BdbQuitExceptHook:
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


class _K3Pdb(pdb.Pdb):
    """`Pdb`, освобождающий консоль К3 по завершении сессии отладки.

    `bdb.Bdb.set_trace` лишь взводит трассировку и сразу возвращает
    управление — интерактивная сессия начинается позже, при
    выполнении следующей отслеживаемой строки. Поэтому закрывать
    консоль сразу после вызова `set_trace` нельзя: это приведёт к
    остановке отладчика внутри собственного кода модуля вместо кода
    вызывающей функции. Консоль корректно освобождается из точек,
    в которых сессия действительно завершается: `q`/`quit`,
    `c`/`continue` или Ctrl+C.
    """

    def __init__(
        self, console: _DebugConsole, *args: Any, **kwargs: Any
    ) -> None:
        """Связать сессию `pdb` с консолью, которую нужно закрыть."""
        super().__init__(*args, **kwargs)
        self._console = console

    def do_quit(self, arg: str) -> bool:
        """Обработать команду `q`/`quit` и закрыть консоль К3."""
        result = super().do_quit(arg)
        self._console.release()
        return bool(result)

    do_q = do_quit

    def do_continue(self, arg: str) -> bool:
        """Обработать команду `c`/`continue` и закрыть консоль К3."""
        result = super().do_continue(arg)
        self._console.release()
        return bool(result)

    do_c = do_cont = do_continue

    def _cmdloop(self) -> None:
        """Запустить цикл команд, завершая его по Ctrl+C.

        Базовая реализация `pdb` гасит `KeyboardInterrupt` и повторно
        запрашивает команду. По требованиям к этому отладчику Ctrl+C
        должен, как и `q`, завершать сессию и закрывать консоль.
        """
        try:
            self.cmdloop()
        except KeyboardInterrupt:
            self.message("")
            self.set_quit()
            self._console.release()


class _ConditionalTrace:
    """Декоратор, запускающий сессию `pdb` при входе в функцию.

    Возвращается методом `_K3Debugger.set_trace`, вызванным с
    именованным аргументом `enable` (`k3_pdb.set_trace(enable=...)`).
    Если `enable` равен `False`, декорируемая функция вызывается без
    каких-либо изменений — консоль отладчика не открывается.
    """

    def __init__(self, debugger: _K3Debugger, enable: bool) -> None:
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


class _K3Debugger:
    """Точка входа отладчика: открывает консоль К3 и запускает `pdb`.

    Объединяет консоль (`_DebugConsole`), подмену `sys.excepthook`
    (`_BdbQuitExceptHook`) и сессию `pdb` (`_K3Pdb`) в единый сценарий
    `set_trace`, используемый как `k3_pdb.set_trace`/`k3_pdb.breakpoint`.
    """

    def __init__(self) -> None:
        """Создать собственные консоль и обработчик исключений."""
        self._console = _DebugConsole()
        self._excepthook = _BdbQuitExceptHook()

    @overload
    def set_trace(self, enable: None = ...) -> None: ...

    @overload
    def set_trace(self, enable: bool) -> _ConditionalTrace: ...

    def set_trace(
        self, enable: bool | None = None
    ) -> _ConditionalTrace | None:
        """Остановиться в вызывающем коде либо вернуть декоратор.

        Без аргументов (`k3_pdb.set_trace()`) открывает консоль К3 и
        останавливается в коде вызывающей функции — как обычный
        `pdb.set_trace()`. С именованным аргументом `enable`
        (`k3_pdb.set_trace(enable=True/False)`) возвращает декоратор
        (`_ConditionalTrace`), который запускает сессию `pdb` при
        входе в декорируемую функцию, если `enable` равен `True`, и
        не делает ничего, если `enable` равен `False`.

        После взведения трассировки метод не должен выполнять никакой
        код: вызов `bdb.Bdb.set_trace` не блокирует выполнение, и
        любой последующий вызов Python-функции получил бы управление
        раньше вызывающего кода, из-за чего интерактивная сессия
        ошибочно стартовала бы внутри `set_trace`, а не в кадре
        вызывающей функции.
        """
        if enable is not None:
            return _ConditionalTrace(self, enable)

        self._excepthook.ensure_installed()
        self._console.enable()
        self._console.setup_streams()

        caller_frame = sys._getframe().f_back # pyright: ignore[reportPrivateUsage]

        debugger = _K3Pdb(
            self._console,
            stdin=self._console.stdin,
            stdout=self._console.stdout,
        )

        self._console.active = True
        debugger.set_trace(caller_frame)
        return None


_debugger = _K3Debugger()

set_trace = _debugger.set_trace

# Алиас, чтобы можно было использовать k3_pdb.breakpoint(), как в
# встроенном breakpoint().
breakpoint = set_trace
