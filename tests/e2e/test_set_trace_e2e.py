"""E2e-тесты реальной интерактивной сессии set_trace/breakpoint.

Проверяют полный, не подменённый набор классов пакета — K3Debugger,
K3Pdb, DebugConsole, BdbQuitExceptHook и ConditionalTrace работают
здесь по-настоящему вместе. Подставлен только физический ввод/вывод
консоли (см. console_helpers) — реальное приложение К3-Мебель не
требуется, достаточно того, что процесс запущен из обычной консоли.
"""

from __future__ import annotations

import sys
import unittest

import console_helpers

from src.k3_pdb_debugger import debugger


class TestSetTraceEndToEnd(unittest.TestCase):
    """Реальная сессия pdb, запущенная через K3Debugger.set_trace()."""

    def setUp(self) -> None:
        """Убедиться, что тест запущен из реальной консоли."""
        console_helpers.require_console()
        self.debugger_instance = debugger.K3Debugger()
        self.addCleanup(setattr, sys, "stdin", sys.stdin)
        self.addCleanup(setattr, sys, "stdout", sys.stdout)
        self.addCleanup(setattr, sys, "stderr", sys.stderr)

    def test_continue_resumes_execution_after_breakpoint(self) -> None:
        """Команда c должна по-настоящему возобновить работу функции."""
        calls: list[str] = []

        def target() -> int:
            calls.append("before")
            self.debugger_instance.set_trace()
            calls.append("after")
            return 42

        with console_helpers.scripted_input("c"):
            result = target()

        self.assertEqual(result, 42)
        self.assertEqual(calls, ["before", "after"])
        self.assertFalse(self.debugger_instance._console.active)

    def test_step_then_continue_executes_statement_by_statement(
        self,
    ) -> None:
        """Команда n должна выполнить ровно одну строку за раз."""
        calls: list[str] = []

        def target() -> str:
            self.debugger_instance.set_trace()
            calls.append("first")
            calls.append("second")
            return "done"

        with console_helpers.scripted_input("n", "c"):
            result = target()

        self.assertEqual(result, "done")
        self.assertEqual(calls, ["first", "second"])

    def test_quit_raises_bdbquit_out_of_the_paused_frame(self) -> None:
        """Команда q должна прервать функцию через bdb.BdbQuit."""
        import bdb

        def target() -> None:
            self.debugger_instance.set_trace()
            raise AssertionError("не должно выполниться после q")

        with console_helpers.scripted_input("q"):
            with self.assertRaises(bdb.BdbQuit):
                target()

        self.assertFalse(self.debugger_instance._console.active)


class TestConditionalTraceEndToEnd(unittest.TestCase):
    """Реальная сессия pdb через декоратор set_trace(enable=...)."""

    def setUp(self) -> None:
        """Убедиться, что тест запущен из реальной консоли."""
        console_helpers.require_console()
        self.debugger_instance = debugger.K3Debugger()
        self.addCleanup(setattr, sys, "stdin", sys.stdin)
        self.addCleanup(setattr, sys, "stdout", sys.stdout)
        self.addCleanup(setattr, sys, "stderr", sys.stderr)

    def test_enabled_decorator_runs_real_debug_session(self) -> None:
        """enable=True должен по-настоящему открыть сессию pdb."""

        @self.debugger_instance.set_trace(enable=True)
        def target(a: int, b: int) -> int:
            return a + b

        with console_helpers.scripted_input("c"):
            result = target(2, 3)

        self.assertEqual(result, 5)

    def test_disabled_decorator_skips_debug_session_entirely(self) -> None:
        """enable=False не должен трогать консоль вообще."""

        @self.debugger_instance.set_trace(enable=False)
        def target(a: int, b: int) -> int:
            return a + b

        result = target(2, 3)

        self.assertEqual(result, 5)
        self.assertFalse(self.debugger_instance._console.active)


if __name__ == "__main__":
    unittest.main()
