"""E2e-тест реального завершения сессии отладчика по команде q/quit.

Запускает tests/e2e/fixtures/quit_target.py отдельным процессом, чтобы
по-настоящему проверить замену трейсбека bdb.BdbQuit коротким
сообщением в sys.excepthook (BdbQuitExceptHook) — это наблюдаемо
только когда исключение доходит необработанным до самого верха
процесса. Реальное приложение К3-Мебель для этого не требуется.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest

import console_helpers

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)


class TestQuitEndToEnd(unittest.TestCase):
    """Необработанный BdbQuit должен превращаться в короткое сообщение."""

    def setUp(self) -> None:
        """Убедиться, что тест запущен из реальной консоли."""
        console_helpers.require_console()

    def test_quit_replaces_traceback_with_short_message(self) -> None:
        """Дочерний процесс печатает сообщение вместо трейсбека."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tests.e2e.fixtures.quit_target",
            ],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            timeout=30,
        )

        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn("Выход из режима отладки", result.stdout)
        self.assertNotIn("Traceback", result.stdout)
        self.assertNotIn("UNREACHABLE-AFTER-QUIT", result.stdout)


if __name__ == "__main__":
    unittest.main()
