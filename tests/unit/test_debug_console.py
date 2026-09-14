"""Тесты консоли отладчика."""

from __future__ import annotations

import sys
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from src.k3_pdb_debugger import io


class TestDebugConsole(unittest.TestCase):
    """Тест консоли отладчика (DebugConsole)."""

    @patch.object(io._thread, "interrupt_main")
    def test_ctrl_c_interrupts_main_thread_when_active(
        self, mock_interrupt_main: Any
    ):
        """Активная сессия pdb должна прерываться через interrupt_main."""
        console = io.DebugConsole()
        console.active = True

        result = console._on_ctrl_event(io.CTRL_C_EVENT)

        mock_interrupt_main.assert_called_once()
        self.assertTrue(result)

    @patch.object(io._thread, "interrupt_main")
    def test_ctrl_c_does_not_interrupt_when_inactive(
        self, mock_interrupt_main: Any
    ):
        """Вне сессии pdb Ctrl+C не должен ничего прерывать."""
        console = io.DebugConsole()
        console.active = False

        result = console._on_ctrl_event(io.CTRL_C_EVENT)

        mock_interrupt_main.assert_not_called()
        self.assertTrue(result)

    @patch.object(io._thread, "interrupt_main")
    def test_ctrl_c_always_reports_handled_to_protect_k3_process(
        self, mock_interrupt_main: Any
    ):
        """CTRL_C_EVENT всегда должен считаться обработанным.

        Regression-тест: если вернуть False, а другого обработчика,
        возвращающего True, не окажется (типично для встраиваемого
        в К3-Мебель интерпретатора без initsigs), Windows применяет
        действие по умолчанию — завершает весь процесс К3-Мебель.
        """
        console = io.DebugConsole()
        for active in (True, False):
            with self.subTest(active=active):
                console.active = active
                result = console._on_ctrl_event(io.CTRL_C_EVENT)
                self.assertTrue(result)

    def test_other_events_are_not_handled(self):
        """Прочие консольные события обработчик не перехватывает."""
        console = io.DebugConsole()

        result = console._on_ctrl_event(io.CTRL_C_EVENT + 1)

        self.assertFalse(result)

    @patch("sys.settrace")
    @patch.object(io, "kernel32")
    def test_detach_restores_original_streams_and_closes_streams(
        self, mock_kernel32: Any, mock_settrace: Any
    ):
        """Потоки К3 восстанавливаются, файлы консоли закрываются.

        `sys.settrace` подменяется, чтобы вызов реального
        `sys.settrace(None)` внутри `detach` не снимал собственный
        трассировщик coverage.py для всех тестов, идущих после этого.
        """
        console = io.DebugConsole()
        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        console.stdin = mock_stdin
        console.stdout = mock_stdout

        console.detach()

        mock_settrace.assert_called_once_with(None)
        mock_stdin.close.assert_called_once()
        mock_stdout.close.assert_called_once()
        self.assertIsNone(console.stdin)
        self.assertIsNone(console.stdout)
        mock_kernel32.FreeConsole.assert_not_called()

    @patch("sys.settrace")
    @patch.object(io, "kernel32")
    def test_detach_frees_console_and_removes_ctrl_handler_when_created(
        self, mock_kernel32: Any, mock_settrace: Any
    ):
        """Созданную консоль нужно освободить вместе с хендлером."""
        console = io.DebugConsole()
        console._created = True
        sentinel_handler = MagicMock()
        console._ctrl_handler = sentinel_handler

        console.detach()

        mock_kernel32.SetConsoleCtrlHandler.assert_called_once_with(
            sentinel_handler, False
        )
        mock_kernel32.FreeConsole.assert_called_once()
        mock_settrace.assert_called_once_with(None)
        self.assertFalse(console._created)
        self.assertIsNone(console._ctrl_handler)

    @patch("sys.settrace")
    @patch.object(io, "kernel32")
    def test_detach_is_safe_to_call_when_nothing_was_set_up(
        self, mock_kernel32: Any, mock_settrace: Any
    ):
        """Повторный/пустой вызов detach не должен падать."""
        console = io.DebugConsole()

        console.detach()

        mock_kernel32.FreeConsole.assert_not_called()
        mock_settrace.assert_called_once_with(None)

    @patch("sys.settrace")
    @patch.object(io, "kernel32")
    def test_detach_ignores_oserror_when_closing_stdin(
        self, mock_kernel32: Any, mock_settrace: Any
    ):
        """OSError при закрытии stdin не должен прерывать detach."""
        console = io.DebugConsole()
        mock_stdin = MagicMock()
        mock_stdin.close.side_effect = OSError("already closed")
        console.stdin = mock_stdin

        console.detach()

        mock_stdin.close.assert_called_once()
        self.assertIsNone(console.stdin)

    @patch("sys.settrace")
    @patch.object(io, "kernel32")
    def test_detach_ignores_oserror_when_closing_stdout(
        self, mock_kernel32: Any, mock_settrace: Any
    ):
        """OSError при закрытии stdout не должен прерывать detach."""
        console = io.DebugConsole()
        mock_stdout = MagicMock()
        mock_stdout.close.side_effect = OSError("already closed")
        console.stdout = mock_stdout

        console.detach()

        mock_stdout.close.assert_called_once()
        self.assertIsNone(console.stdout)

    @patch.object(io, "kernel32")
    def test_enable_skips_alloc_when_console_already_exists(
        self, mock_kernel32: Any
    ):
        """Если консоль К3 уже открыта, повторно её создавать не нужно."""
        mock_kernel32.GetConsoleWindow.return_value = 123

        console = io.DebugConsole()
        console.enable()

        mock_kernel32.AllocConsole.assert_not_called()
        self.assertFalse(console._created)

    @patch.object(io.ctypes, "WinError")
    @patch.object(io, "kernel32")
    def test_enable_raises_when_alloc_console_fails(
        self, mock_kernel32: Any, mock_win_error: Any
    ):
        """Если AllocConsole не смог создать окно, нужно поднять ошибку."""
        mock_kernel32.GetConsoleWindow.return_value = 0
        mock_kernel32.AllocConsole.return_value = 0
        mock_win_error.return_value = OSError("alloc failed")

        console = io.DebugConsole()

        with self.assertRaises(OSError):
            console.enable()

        self.assertFalse(console._created)

    @patch.object(io, "PHANDLER_ROUTINE")
    @patch.object(io, "kernel32")
    def test_enable_creates_console_and_installs_ctrl_handler(
        self, mock_kernel32: Any, mock_phandler_routine: Any
    ):
        """Успешное создание консоли должно устанавливать обработчик."""
        mock_kernel32.GetConsoleWindow.return_value = 0
        mock_kernel32.AllocConsole.return_value = 1
        sentinel_handler = MagicMock()
        mock_phandler_routine.return_value = sentinel_handler

        console = io.DebugConsole()
        console.enable()

        self.assertTrue(console._created)
        self.assertIs(console._ctrl_handler, sentinel_handler)
        mock_kernel32.SetConsoleCtrlHandler.assert_called_once_with(
            sentinel_handler, True
        )

    def test_setup_streams_redirects_stdin_stdout_stderr(self):
        """stdin/stdout/stderr должны переключиться на потоки консоли."""
        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        self.addCleanup(setattr, sys, "stdin", sys.stdin)
        self.addCleanup(setattr, sys, "stdout", sys.stdout)
        self.addCleanup(setattr, sys, "stderr", sys.stderr)

        console = io.DebugConsole()

        with patch(
            "builtins.open", side_effect=[mock_stdin, mock_stdout]
        ) as mock_open:
            console.setup_streams()

        mock_open.assert_any_call("CONIN$")
        mock_open.assert_any_call("CONOUT$", "w", buffering=1)
        self.assertIs(console.stdin, mock_stdin)
        self.assertIs(console.stdout, mock_stdout)
        self.assertIs(sys.stdin, mock_stdin)
        self.assertIs(sys.stdout, mock_stdout)
        self.assertIs(sys.stderr, mock_stdout)

    @patch.object(io.DebugConsole, "detach")
    def test_release_clears_active_flag_and_detaches(self, mock_detach: Any):
        """Release должна сбрасывать флаг активности и закрывать консоль."""
        console = io.DebugConsole()
        console.active = True

        console.release()

        self.assertFalse(console.active)
        mock_detach.assert_called_once()


if __name__ == "__main__":
    unittest.main()
