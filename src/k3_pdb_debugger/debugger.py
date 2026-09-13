"""Реализация отладчика."""

from __future__ import annotations

import pdb
import sys
from typing import Any, overload

from .decorator import ConditionalTrace
from .io import DebugConsole
from .runtime import BdbQuitExceptHook


class K3Pdb(pdb.Pdb):
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
        self, console: DebugConsole, *args: Any, **kwargs: Any
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


class K3Debugger:
    """Точка входа отладчика: открывает консоль К3 и запускает `pdb`.

    Объединяет консоль (`DebugConsole`), подмену `sys.excepthook`
    (`_BdbQuitExceptHook`) и сессию `pdb` (`_K3Pdb`) в единый сценарий
    `set_trace`, используемый как `k3_pdb.set_trace`/`k3_pdb.breakpoint`.
    """

    def __init__(self) -> None:
        """Создать собственные консоль и обработчик исключений."""
        self._console = DebugConsole()
        self._excepthook = BdbQuitExceptHook()

    @overload
    def set_trace(self, enable: None = ...) -> None: ...

    @overload
    def set_trace(self, enable: bool) -> ConditionalTrace: ...

    def set_trace(self, enable: bool | None = None) -> ConditionalTrace | None:
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
            return ConditionalTrace(self, enable)

        self._excepthook.ensure_installed()
        self._console.enable()
        self._console.setup_streams()

        caller_frame = sys._getframe().f_back  # pyright: ignore[reportPrivateUsage]

        debugger = K3Pdb(
            self._console,
            stdin=self._console.stdin,
            stdout=self._console.stdout,
        )

        self._console.active = True
        debugger.set_trace(caller_frame)
        return None
