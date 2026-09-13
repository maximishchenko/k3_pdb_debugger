"""Обработка поведения выхода из отладчика."""

from __future__ import annotations

import bdb
import sys
from types import TracebackType

_QUIT_MESSAGE = "Выход из режима отладки"


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
