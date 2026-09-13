"""Тесты среды запуска PDB."""

from __future__ import annotations

import bdb
import sys
import unittest
from unittest.mock import MagicMock, patch

from src.k3_pdb_debugger import runtime


class TestBdbQuitExceptHook(unittest.TestCase):
    """Тест перехвата BdbQuit в sys.excepthook (BdbQuitExceptHook)."""

    def test_bdb_quit_is_replaced_with_short_message(self):
        """BdbQuit не должен показываться в консоли К3 трейсбеком."""
        hook = runtime.BdbQuitExceptHook()
        hook._original = MagicMock()

        with patch("builtins.print") as mock_print:
            hook(bdb.BdbQuit, bdb.BdbQuit(), None)

        mock_print.assert_called_once_with(runtime._QUIT_MESSAGE)
        hook._original.assert_not_called()

    def test_other_exceptions_are_forwarded_unchanged(self):
        """Прочие исключения должны обрабатываться как обычно."""
        hook = runtime.BdbQuitExceptHook()
        hook._original = MagicMock()
        exc_value = ValueError("boom")

        hook(ValueError, exc_value, None)

        hook._original.assert_called_once_with(ValueError, exc_value, None)

    def test_ensure_installed_replaces_hook_once(self):
        """Хук должен подменяться единожды и указывать на себя."""
        hook = runtime.BdbQuitExceptHook()
        original_hook = sys.excepthook
        try:
            sys.excepthook = original_hook

            hook.ensure_installed()
            self.assertIs(sys.excepthook, hook)

            sys.excepthook = original_hook
            hook.ensure_installed()
            self.assertIs(sys.excepthook, original_hook)
        finally:
            sys.excepthook = original_hook


if __name__ == "__main__":
    unittest.main()
