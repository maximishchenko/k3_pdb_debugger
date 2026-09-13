"""Обработчик запуска python отладчика pdb в среде приложения К3-Мебель."""

from . import debugger, decorator, io, runtime

debugger_instance = debugger.K3Debugger()

set_trace = debugger_instance.set_trace

# Алиас, чтобы можно было использовать текущий breakpoint(), как в
# встроенном breakpoint().
breakpoint = set_trace

__all__ = ["breakpoint", "debugger", "decorator", "io", "runtime", "set_trace"]
