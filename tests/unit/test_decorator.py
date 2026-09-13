"""Тест декоратора."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from src.k3_pdb_debugger import decorator


class TestConditionalTrace(unittest.TestCase):
    """Тест декоратора условного запуска отладки (ConditionalTrace)."""

    def test_disabled_decorator_returns_function_unchanged(self):
        """enable=False должен возвращать исходную функцию как есть."""
        debugger = MagicMock()

        def func(a: int | float, b: int | float) -> int | float:
            return a + b

        decorated = decorator.ConditionalTrace(debugger, False)(func)

        self.assertIs(decorated, func)
        debugger.set_trace.assert_not_called()

    def test_enabled_decorator_starts_trace_before_calling_function(self):
        """enable=True должен запускать set_trace перед вызовом функции."""
        debugger = MagicMock()
        calls: list[Any] = []
        debugger.set_trace.side_effect = lambda: calls.append("set_trace")

        def func(a: int | float, b: int | float) -> int | float:
            calls.append("func")
            return a + b

        decorated = decorator.ConditionalTrace(debugger, True)(func)
        result = decorated(2, 3)

        self.assertEqual(result, 5)
        self.assertEqual(calls, ["set_trace", "func"])

    def test_enabled_decorator_preserves_function_metadata(self):
        """functools.wraps должен сохранять имя декорируемой функции."""
        debugger = MagicMock()

        def func(a: int | float, b: int | float) -> int | float:
            return a + b

        decorated = decorator.ConditionalTrace(debugger, True)(func)

        self.assertEqual(decorated.__name__, "func")


if __name__ == "__main__":
    unittest.main()
