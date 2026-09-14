"""Реальный сценарий выхода из отладчика по команде q.

Запускается отдельным процессом (см. test_quit_e2e.py), а не внутри
тестового метода: sys.excepthook перехватывает исключение только
тогда, когда оно действительно доходит необработанным до самого верха
процесса — этого нельзя показать, вызвав код напрямую внутри теста,
там необработанный BdbQuit поймает сам unittest, а не excepthook.

Импортирует пакет через каталог src так же, как это делают examples/
в этом репозитории (модуль запускается как `python -m
tests.e2e.fixtures.quit_target` из корня репозитория).
"""

from __future__ import annotations

import os
import sys

from src.k3_pdb_debugger import io, set_trace

_stdin_read_fd, _stdin_write_fd = os.pipe()
os.write(_stdin_write_fd, b"q\n")
os.close(_stdin_write_fd)


def _scripted_setup_streams(self: io.DebugConsole) -> None:
    """Открыть подставные потоки вместо CONIN$/CONOUT$."""
    self.stdin = os.fdopen(_stdin_read_fd, "r", encoding="utf-8")
    self.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    sys.stdin = self.stdin
    sys.stdout = self.stdout
    sys.stderr = self.stdout


io.DebugConsole.setup_streams = (  # type: ignore[method-assign]
    _scripted_setup_streams
)


def target() -> None:
    """Остановиться в точке останова и (не) продолжить работу."""
    set_trace()
    print("UNREACHABLE-AFTER-QUIT")


target()
