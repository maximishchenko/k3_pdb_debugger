"""Обработчик запуска python отладчика pdb в среде приложения К3-Мебель."""

from . import k3_pdb

debugger = k3_pdb.K3Debugger()

set_trace = debugger.set_trace

# Алиас, чтобы можно было использовать k3_pdb.breakpoint(), как в
# встроенном breakpoint().
breakpoint = set_trace

__all__ = ["breakpoint", "debugger", "set_trace"]
