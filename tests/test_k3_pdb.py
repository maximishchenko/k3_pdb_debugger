"""Тест консольного pdb-отладчика К3 (k3_pdb)."""

import bdb
import sys
import unittest
from unittest.mock import MagicMock, patch

from src.k3_pdb_debugger import k3_pdb


class TestDebugConsole(unittest.TestCase):
    """Тест консоли отладчика (_DebugConsole)."""

    @patch.object(k3_pdb._thread, "interrupt_main")
    def test_ctrl_c_interrupts_main_thread_when_active(
        self, mock_interrupt_main
    ):
        """Активная сессия pdb должна прерываться через interrupt_main."""
        console = k3_pdb._DebugConsole()
        console.active = True

        result = console._on_ctrl_event(k3_pdb.CTRL_C_EVENT)

        mock_interrupt_main.assert_called_once()
        self.assertTrue(result)

    @patch.object(k3_pdb._thread, "interrupt_main")
    def test_ctrl_c_does_not_interrupt_when_inactive(
        self, mock_interrupt_main
    ):
        """Вне сессии pdb Ctrl+C не должен ничего прерывать."""
        console = k3_pdb._DebugConsole()
        console.active = False

        result = console._on_ctrl_event(k3_pdb.CTRL_C_EVENT)

        mock_interrupt_main.assert_not_called()
        self.assertTrue(result)

    @patch.object(k3_pdb._thread, "interrupt_main")
    def test_ctrl_c_always_reports_handled_to_protect_k3_process(
        self, mock_interrupt_main
    ):
        """CTRL_C_EVENT всегда должен считаться обработанным.

        Regression-тест: если вернуть False, а другого обработчика,
        возвращающего True, не окажется (типично для встраиваемого
        в К3-Мебель интерпретатора без initsigs), Windows применяет
        действие по умолчанию — завершает весь процесс К3-Мебель.
        """
        console = k3_pdb._DebugConsole()
        for active in (True, False):
            with self.subTest(active=active):
                console.active = active
                result = console._on_ctrl_event(k3_pdb.CTRL_C_EVENT)
                self.assertTrue(result)

    def test_other_events_are_not_handled(self):
        """Прочие консольные события обработчик не перехватывает."""
        console = k3_pdb._DebugConsole()

        result = console._on_ctrl_event(k3_pdb.CTRL_C_EVENT + 1)

        self.assertFalse(result)

    @patch.object(k3_pdb, "kernel32")
    def test_detach_restores_original_streams_and_closes_streams(
        self, mock_kernel32
    ):
        """Потоки К3 восстанавливаются, файлы консоли закрываются."""
        console = k3_pdb._DebugConsole()
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

    @patch.object(k3_pdb, "kernel32")
    def test_detach_frees_console_and_removes_ctrl_handler_when_created(
        self, mock_kernel32
    ):
        """Созданную консоль нужно освободить вместе с хендлером."""
        console = k3_pdb._DebugConsole()
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

    @patch.object(k3_pdb, "kernel32")
    def test_detach_is_safe_to_call_when_nothing_was_set_up(
        self, mock_kernel32
    ):
        """Повторный/пустой вызов detach не должен падать."""
        console = k3_pdb._DebugConsole()

        console.detach()

        mock_kernel32.FreeConsole.assert_not_called()

    @patch.object(k3_pdb._DebugConsole, "detach")
    def test_release_clears_active_flag_and_detaches(self, mock_detach):
        """Release должна сбрасывать флаг активности и закрывать консоль."""
        console = k3_pdb._DebugConsole()
        console.active = True

        console.release()

        self.assertFalse(console.active)
        mock_detach.assert_called_once()


class TestBdbQuitExceptHook(unittest.TestCase):
    """Тест перехвата BdbQuit в sys.excepthook (_BdbQuitExceptHook)."""

    def test_bdb_quit_is_replaced_with_short_message(self):
        """BdbQuit не должен показываться в консоли К3 трейсбеком."""
        hook = k3_pdb._BdbQuitExceptHook()
        hook._original = MagicMock()

        with patch("builtins.print") as mock_print:
            hook(bdb.BdbQuit, bdb.BdbQuit(), None)

        mock_print.assert_called_once_with(k3_pdb._QUIT_MESSAGE)
        hook._original.assert_not_called()

    def test_other_exceptions_are_forwarded_unchanged(self):
        """Прочие исключения должны обрабатываться как обычно."""
        hook = k3_pdb._BdbQuitExceptHook()
        hook._original = MagicMock()
        exc_value = ValueError("boom")

        hook(ValueError, exc_value, None)

        hook._original.assert_called_once_with(ValueError, exc_value, None)

    def test_ensure_installed_replaces_hook_once(self):
        """Хук должен подменяться единожды и указывать на себя."""
        hook = k3_pdb._BdbQuitExceptHook()
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


class TestK3Pdb(unittest.TestCase):
    """Тест сессии отладчика _K3Pdb."""

    def test_do_quit_releases_console_after_default_behaviour(self):
        """Команда q/quit должна закрывать консоль К3."""
        console = MagicMock()
        debugger = k3_pdb._K3Pdb(console)
        debugger.reset()

        result = debugger.do_quit("")

        self.assertTrue(result)
        self.assertTrue(debugger.quitting)
        console.release.assert_called_once()

    def test_do_continue_releases_console_after_default_behaviour(self):
        """Команда c/continue должна закрывать консоль К3."""
        console = MagicMock()
        debugger = k3_pdb._K3Pdb(console)
        debugger.reset()

        result = debugger.do_continue("")

        self.assertTrue(result)
        console.release.assert_called_once()

    def test_do_q_is_alias_for_do_quit(self):
        """do_q должна быть тем же обработчиком, что и do_quit."""
        self.assertIs(k3_pdb._K3Pdb.do_q, k3_pdb._K3Pdb.do_quit)

    def test_do_c_and_do_cont_are_aliases_for_do_continue(self):
        """do_c и do_cont — тот же обработчик, что и do_continue."""
        self.assertIs(k3_pdb._K3Pdb.do_c, k3_pdb._K3Pdb.do_continue)
        self.assertIs(k3_pdb._K3Pdb.do_cont, k3_pdb._K3Pdb.do_continue)

    def test_cmdloop_keyboard_interrupt_quits_and_releases_console(self):
        """Ctrl+C во время сессии должен завершать её и закрывать консоль."""
        console = MagicMock()
        debugger = k3_pdb._K3Pdb(console)

        with patch.object(debugger, "cmdloop", side_effect=KeyboardInterrupt):
            with patch.object(debugger, "set_quit") as mock_set_quit:
                debugger._cmdloop()

        mock_set_quit.assert_called_once()
        console.release.assert_called_once()

    def test_cmdloop_normal_exit_does_not_release_console(self):
        """Промежуточная остановка (n/s) не должна закрывать консоль."""
        console = MagicMock()
        debugger = k3_pdb._K3Pdb(console)

        with patch.object(debugger, "cmdloop", return_value=None):
            debugger._cmdloop()

        console.release.assert_not_called()


class TestConditionalTrace(unittest.TestCase):
    """Тест декоратора условного запуска отладки (_ConditionalTrace)."""

    def test_disabled_decorator_returns_function_unchanged(self):
        """enable=False должен возвращать исходную функцию как есть."""
        debugger = MagicMock()

        def func(a, b):
            return a + b

        decorated = k3_pdb._ConditionalTrace(debugger, False)(func)

        self.assertIs(decorated, func)
        debugger.set_trace.assert_not_called()

    def test_enabled_decorator_starts_trace_before_calling_function(self):
        """enable=True должен запускать set_trace перед вызовом функции."""
        debugger = MagicMock()
        calls = []
        debugger.set_trace.side_effect = lambda: calls.append("set_trace")

        def func(a, b):
            calls.append("func")
            return a + b

        decorated = k3_pdb._ConditionalTrace(debugger, True)(func)
        result = decorated(2, 3)

        self.assertEqual(result, 5)
        self.assertEqual(calls, ["set_trace", "func"])

    def test_enabled_decorator_preserves_function_metadata(self):
        """functools.wraps должен сохранять имя декорируемой функции."""
        debugger = MagicMock()

        def func(a, b):
            return a + b

        decorated = k3_pdb._ConditionalTrace(debugger, True)(func)

        self.assertEqual(decorated.__name__, "func")


class TestK3Debugger(unittest.TestCase):
    """Тест точки входа отладчика (_K3Debugger.set_trace)."""

    def test_arms_debugger_for_immediate_caller_frame_only(self):
        """set_trace не должна выполнять код после взведения трассировки.

        Regression-тест: раньше set_trace вызывала debugger.set_continue()
        и detach() сразу после debugger.set_trace(), из-за чего
        отладчик останавливался внутри собственного кода модуля вместо
        кадра вызывающей функции.
        """
        debugger = k3_pdb._K3Debugger()
        debugger._console = MagicMock()
        debugger._console.stdin = object()
        debugger._console.stdout = object()
        debugger._excepthook = MagicMock()

        with patch.object(k3_pdb, "_K3Pdb") as mock_pdb_cls:
            mock_pdb_instance = mock_pdb_cls.return_value

            def caller():
                debugger.set_trace()

            caller()

        debugger._excepthook.ensure_installed.assert_called_once()
        debugger._console.enable.assert_called_once()
        debugger._console.setup_streams.assert_called_once()
        mock_pdb_cls.assert_called_once_with(
            debugger._console,
            stdin=debugger._console.stdin,
            stdout=debugger._console.stdout,
        )
        self.assertTrue(debugger._console.active)

        mock_pdb_instance.set_trace.assert_called_once()
        called_frame = mock_pdb_instance.set_trace.call_args[0][0]
        self.assertEqual(called_frame.f_code.co_name, "caller")

        mock_pdb_instance.set_continue.assert_not_called()
        debugger._console.detach.assert_not_called()

    def test_set_trace_without_arguments_returns_none(self):
        """set_trace() без аргументов должен работать как раньше."""
        debugger = k3_pdb._K3Debugger()
        debugger._console = MagicMock()
        debugger._console.stdin = object()
        debugger._console.stdout = object()
        debugger._excepthook = MagicMock()

        with patch.object(k3_pdb, "_K3Pdb"):
            result = debugger.set_trace()

        self.assertIsNone(result)

    def test_set_trace_with_enable_returns_conditional_trace(self):
        """set_trace(enable=...) должен возвращать декоратор."""
        debugger = k3_pdb._K3Debugger()

        for enable in (True, False):
            with self.subTest(enable=enable):
                decorator = debugger.set_trace(enable=enable)
                self.assertIsInstance(decorator, k3_pdb._ConditionalTrace)
                self.assertIs(decorator._debugger, debugger)
                self.assertIs(decorator._enable, enable)

    def test_set_trace_module_attribute_is_bound_to_singleton(self):
        """k3_pdb.set_trace должен быть методом модульного экземпляра."""
        self.assertEqual(k3_pdb.set_trace, k3_pdb._debugger.set_trace)

    def test_breakpoint_alias_points_to_set_trace(self):
        """k3_pdb.breakpoint должна быть алиасом k3_pdb.set_trace."""
        self.assertIs(k3_pdb.breakpoint, k3_pdb.set_trace)


if __name__ == "__main__":
    unittest.main()
