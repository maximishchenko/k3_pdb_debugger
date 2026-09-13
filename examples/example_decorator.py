"""Пример использования в качестве декоратора."""

from __future__ import annotations

from src.k3_pdb_debugger import set_trace


@set_trace(enable=True)
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
    ab = ab / 10
    return ab


def main() -> None:
    """Точка входа."""
    function(4, 3)


if __name__ == "__main__":
    main()
