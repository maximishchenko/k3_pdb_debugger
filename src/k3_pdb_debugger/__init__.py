"""Консольный `pdb` для К3-Мебель с изолированным окном отладчика.

Пакет открывает отдельное консольное окно Windows и перенаправляет в
него `stdin`/`stdout`/`stderr` на время интерактивной сессии `pdb`,
не затрагивая собственные потоки ввода-вывода процесса `mebel.exe`.
Команды `q`/`quit`, `c`/`continue` и Ctrl+C корректно завершают
сессию отладчика и закрывают консольное окно, не завершая при этом
процесс К3-Мебель. `q`/Ctrl+C, как и в обычном `pdb`, прерывают
выполнение текущей операции через `bdb.BdbQuit`, но трейсбек этого
исключения в консоли К3-Мебель заменяется коротким сообщением.


Для подключения текущего модуля к глобальному вызову breakpoint (начиная
с версии Python 3.7) возможно использовать 2 способа:
1. Установить значение переменной окружения PYTHONBREAKPOINT

```python
from __future__ import annotations

from k3_pdb_debugger import set_trace

set PYTHONBREAKPOINT=set_trace
```

> Пакет `k3_pdb_debugger` должен находиться в области видимости sys.path

2. Перехватить вызов `sys.breakpointhook` глобально

```python
from __future__ import annotations

import sys
from k3_pdb_debugger import set_trace

sys.breakpointhook = set_trace
```

Пример использования:

```python
from __future__ import annotations

import sys

from k3_pdb_debugger import set_trace

sys.breakpointhook = set_trace

def function(a: int | float, b: int | float) -> int | float:
    ab = a ** b
    string = 'example'
    print(string)
    breakpoint()
    ab = ab / 10
    return ab

function(2, 4)
```

`set_trace` из пакета `k3_pdb_debugger` можно также использовать как
декоратор с именованным аргументом `enable`: если `enable` равен `True`,
сессия `pdb` запускается сразу при входе в декорируемую функцию; если
`False` — функция вызывается как обычно, без отладки:

```python
from __future__ import annotations

from k3_pdb_debugger import set_trace

@set_trace(enable=True)  # отладка запускается
def function(a: int | float, b: int | float) -> int | float:
    ...

@k3_pdb.set_trace(enable=False)  # отладка не запускается
def function(a: int | float, b: int | float) -> int | float:
    ...
```
"""

from . import debugger

debugger_instance = debugger.K3Debugger()

set_trace = debugger_instance.set_trace

# Алиас, чтобы можно было использовать текущий breakpoint(), как в
# встроенном breakpoint().
breakpoint = set_trace

__all__ = ["breakpoint", "set_trace"]
