"""Вспомогательные средства для e2e-тестов пакета k3_pdb_debugger.

E2e-тесты, в отличие от unit-тестов (tests/unit), не подменяют классы
самого пакета — K3Debugger, K3Pdb, DebugConsole и BdbQuitExceptHook
работают по-настоящему, вплетая реальный bdb/pdb в реальный код. Из
всего этого нельзя автоматически (без стороннего инструментария вроде
эмуляции нажатий клавиш) подменить лишь последний, физический шаг —
открытие консольных устройств Windows (CONIN$/CONOUT$). Поэтому здесь
подставляется только он: DebugConsole.setup_streams получает вместо
реальных консольных потоков управляемые тестом объекты. Само окно
консоли всё равно должно существовать по-настоящему — DebugConsole
.enable() выполняется как обычно и, если процесс уже прикреплён к
консоли (что и требуется для запуска e2e-тестов), просто не создаёт
новое окно, как и не создало бы его в обычном консольном приложении.
Реальное приложение К3-Мебель для этого не нужно.
"""

from __future__ import annotations

import contextlib
import os
import sys
import unittest
from typing import Generator
from unittest.mock import patch

from src.k3_pdb_debugger import io as k3_io


def require_console() -> None:
    """Пропустить тест, если процесс не прикреплён к реальной консоли.

    E2e-тесты должны запускаться из обычной консоли (терминала), а не,
    например, из полностью headless-окружения без какого-либо окна.
    """
    if not k3_io.kernel32.GetConsoleWindow():
        raise unittest.SkipTest(
            "e2e-тесты требуют реального консольного окна процесса"
        )


@contextlib.contextmanager
def scripted_input(*commands: str) -> Generator[None, None, None]:
    """Подставить сценарий команд pdb вместо набора их на клавиатуре.

    `commands` — команды в порядке ввода, каждая на отдельной строке.
    Последняя должна завершать сессию (`c`/`continue`/`q`/`quit`) —
    иначе чтение следующей команды зависнет в ожидании продолжения
    ввода, которого больше не будет.
    """
    stdin_read_fd, stdin_write_fd = os.pipe()
    script = "".join(command + "\n" for command in commands)
    os.write(stdin_write_fd, script.encode("utf-8"))
    os.close(stdin_write_fd)

    def fake_setup_streams(self: k3_io.DebugConsole) -> None:
        """Открыть подставные потоки вместо CONIN$/CONOUT$."""
        self.stdin = os.fdopen(stdin_read_fd, "r", encoding="utf-8")
        self.stdout = open(  # noqa: SIM115
            os.devnull, "w", encoding="utf-8"
        )
        sys.stdin = self.stdin
        sys.stdout = self.stdout
        sys.stderr = self.stdout

    target = k3_io.DebugConsole
    with patch.object(target, "setup_streams", fake_setup_streams):
        yield
