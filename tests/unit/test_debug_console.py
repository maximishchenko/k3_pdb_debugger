"""Тесты консоли отладчика."""

from __future__ import annotations

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

    @patch.object(io, "kernel32")
    def test_detach_restores_original_streams_and_closes_streams(
        self, mock_kernel32: Any
    ):
        """Потоки К3 восстанавливаются, файлы консоли закрываются."""
        console = io.DebugConsole()
        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        console.stdin = mock_stdin
        console.stdout = mock_stdout

        console.detach()

        mock_stdin.close.assert_called_once()
        mock_stdout.close.assert_called_once()
        self.assertIsNone(console.stdin)
        self.assertIsNone(console.stdout)
        mock_kernel32.FreeConsole.assert_not_called()

    @patch.object(io, "kernel32")
    def test_detach_frees_console_and_removes_ctrl_handler_when_created(
        self, mock_kernel32: Any
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
        self.assertFalse(console._created)
        self.assertIsNone(console._ctrl_handler)

    @patch.object(io, "kernel32")
    def test_detach_is_safe_to_call_when_nothing_was_set_up(
        self, mock_kernel32: Any
    ):
        """Повторный/пустой вызов detach не должен падать."""
        console = io.DebugConsole()

        console.detach()

        mock_kernel32.FreeConsole.assert_not_called()

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
