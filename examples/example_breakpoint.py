"""Пример вызова breakpoint().

Функция доступна в стандартной библиотеке Python, начиная с версии 3.7.
"""

from __future__ import annotations

import sys

from src.k3_pdb_debugger import set_trace

sys.breakpointhook = set_trace


def function(a: int | float, b: int | float) -> int | float:
    """Return (a ** b)/10 .

    Args:
        a (int | float): first argument
        b (int | float): secund argument

    Returns:
        int | float: return value

    """
    ab = a**b
    string = "example"
    print(string)
    breakpoint()
    ab = ab / 10
    return ab


def main() -> None:
    """Запуск функции."""
    function(2, 4)


if __name__ == "__main__":
    main()
