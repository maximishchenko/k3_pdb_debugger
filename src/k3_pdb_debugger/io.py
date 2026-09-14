"""Операции ввода/вывода. Переопределение stdin/stdout."""

from __future__ import annotations

import _thread
import ctypes
import sys
from ctypes import wintypes
from typing import (
    Any,
    TextIO,
)

kernel32: ctypes.WinDLL = ctypes.windll.kernel32

# Сигнатура обработчика для перехвата консольных событий Windows
# (см. SetConsoleCtrlHandler / HandlerRoutine в WinAPI).
PHANDLER_ROUTINE = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
CTRL_C_EVENT = 0


class DebugConsole:
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
