"""Тесты классов отладчика PDB."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.k3_pdb_debugger import breakpoint, debugger, decorator, set_trace


class TestK3Pdb(unittest.TestCase):
    """Тест сессии отладчика K3Pdb."""

    def test_do_quit_releases_console_after_default_behaviour(self):
        """Команда q/quit должна закрывать консоль К3."""
        console = MagicMock()
        debugger_instance = debugger.K3Pdb(console)
        debugger_instance.reset()

        result = debugger_instance.do_quit("")

        self.assertTrue(result)
        self.assertTrue(debugger_instance.quitting)
        console.release.assert_called_once()

    def test_do_continue_releases_console_after_default_behaviour(self):
        """Команда c/continue должна закрывать консоль К3."""
        console = MagicMock()
        debugger_instance = debugger.K3Pdb(console)
        debugger_instance.reset()

        result = debugger_instance.do_continue("")

        self.assertTrue(result)
        console.release.assert_called_once()

    def test_do_q_is_alias_for_do_quit(self):
        """do_q должна быть тем же обработчиком, что и do_quit."""
        self.assertIs(debugger.K3Pdb.do_q, debugger.K3Pdb.do_quit)

    def test_do_c_and_do_cont_are_aliases_for_do_continue(self):
        """do_c и do_cont — тот же обработчик, что и do_continue."""
        self.assertIs(debugger.K3Pdb.do_c, debugger.K3Pdb.do_continue)
        self.assertIs(debugger.K3Pdb.do_cont, debugger.K3Pdb.do_continue)

    def test_cmdloop_keyboard_interrupt_quits_and_releases_console(self):
        """Ctrl+C во время сессии должен завершать её и закрывать консоль."""
        console = MagicMock()
        debugger_instance = debugger.K3Pdb(console)

        with patch.object(
            debugger_instance, "cmdloop", side_effect=KeyboardInterrupt
        ):
            with patch.object(debugger_instance, "set_quit") as mock_set_quit:
                debugger_instance._cmdloop()

        mock_set_quit.assert_called_once()
        console.release.assert_called_once()

    def test_cmdloop_normal_exit_does_not_release_console(self):
        """Промежуточная остановка (n/s) не должна закрывать консоль."""
        console = MagicMock()
        debugger_instance = debugger.K3Pdb(console)

        with patch.object(debugger_instance, "cmdloop", return_value=None):
            debugger_instance._cmdloop()

        console.release.assert_not_called()


class TestK3Debugger(unittest.TestCase):
    """Тест точки входа отладчика (K3Debugger.set_trace)."""

    def test_arms_debugger_for_immediate_caller_frame_only(self):
        """set_trace не должна выполнять код после взведения трассировки.

        Regression-тест: раньше set_trace вызывала debugger.set_continue()
        и detach() сразу после debugger.set_trace(), из-за чего
        отладчик останавливался внутри собственного кода модуля вместо
        кадра вызывающей функции.
        """
        debugger_instance = debugger.K3Debugger()
        debugger_instance._console = MagicMock()
        debugger_instance._console.stdin = object()
        debugger_instance._console.stdout = object()
        debugger_instance._excepthook = MagicMock()

        with patch.object(debugger, "K3Pdb") as mock_pdb_cls:
            mock_pdb_instance = mock_pdb_cls.return_value

            def caller():
                debugger_instance.set_trace()

            caller()

        debugger_instance._excepthook.ensure_installed.assert_called_once()
        debugger_instance._console.enable.assert_called_once()
        debugger_instance._console.setup_streams.assert_called_once()
        mock_pdb_cls.assert_called_once_with(
            debugger_instance._console,
            stdin=debugger_instance._console.stdin,
            stdout=debugger_instance._console.stdout,
        )
        self.assertTrue(debugger_instance._console.active)

        mock_pdb_instance.set_trace.assert_called_once()
        called_frame = mock_pdb_instance.set_trace.call_args[0][0]
        self.assertEqual(called_frame.f_code.co_name, "caller")

        mock_pdb_instance.set_continue.assert_not_called()
        debugger_instance._console.detach.assert_not_called()

    def test_set_trace_without_arguments_returns_none(self):
        """set_trace() без аргументов должен работать как раньше."""
        debugger_instance = debugger.K3Debugger()
        debugger_instance._console = MagicMock()
        debugger_instance._console.stdin = object()
        debugger_instance._console.stdout = object()
        debugger_instance._excepthook = MagicMock()

        with patch.object(debugger, "K3Pdb"):
            result = debugger_instance.set_trace()

        self.assertIsNone(result)

    def test_set_trace_with_enable_returns_conditional_trace(self):
        """set_trace(enable=...) должен возвращать декоратор."""
        debugger_instance = debugger.K3Debugger()

        for enable in (True, False):
            with self.subTest(enable=enable):
                decorator_item = debugger_instance.set_trace(enable=enable)
                self.assertIsInstance(
                    decorator_item, decorator.ConditionalTrace
                )
                self.assertIs(decorator_item._debugger, debugger_instance)
                self.assertIs(decorator_item._enable, enable)

    def test_set_trace_module_attribute_is_bound_to_singleton(self):
        """set_trace должен быть методом модульного экземпляра."""
        self.assertEqual(set_trace, set_trace)

    def test_breakpoint_alias_points_to_set_trace(self):
        """Функция breakpoint должна быть алиасом set_trace."""
        self.assertIs(breakpoint, set_trace)


if __name__ == "__main__":
    unittest.main()
