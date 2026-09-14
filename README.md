# Отладчик PDB в "К3. Мебель"

![logo](/docs/assets/logo.webp)

## Описание

Надстройка для запуска интерактивного отлачика [PDB](https://docs.python.org/3/library/pdb.html), входящего в стандартную библиотеку Python, в приложении [К3 Мебель](https://k3-mebel.ru/).

Может применяться для отладки при разработке скриптов на языке Python для приложения "К3. Мебель".

Позволит произвести быструю отладку без необходимости подключения отладчика интеактивной среды разработки IDE и установки сторонних библиотек, например [ptvsd](https://github.com/microsoft/ptvsd) или [debugpy](https://github.com/microsoft/debugpy) для [VSCode](https://code.visualstudio.com/).

> При использовании перечисленных пакетов совместно с приложением "К3. Мебель" необходимо учитывать следующую информацию:
>
> ptvsd:
>
> - пакет помечен разработчиком как устаревший
> - репозиторий перемещен разрабочиком в архив
> - требует установки [pydevd](https://github.com/fabioz/PyDev.Debugger) в качестве дополнительной зависимости
> - необходимо устанавливать как в виртуальное окружение приложения "К3. Мебель", так и в виртуальное окружение, используемое при разработке (или глобально)
>
> debugpy:
>
> - актуальная версия пакета требует версию Python не ниже 3.8, при этом в составе приложения К3 Мебель используется Python версии 3.7, т.е. запуск актуальной версии невозможен
> - требует установки [pydevd](https://github.com/fabioz/PyDev.Debugger) в качестве дополнительной зависимости
> - необходимо устанавливать как в виртуальное окружение приложения "К3. Мебель", так и в виртуальное окружение, используемое при разработке (или глобально)

Пакет переопределяет `stdin` и `stdout`, запускается в отдельном сеансе командной строки, а также обрабатывает корректное завершение процесса отладчика.

Таким образом функциональность пакета полностью соответствует API отладчика PDB в составе стандартной библиотеки Python версии 3.7.

## Установка

TODO добавить.

## Использование

Пакет открывает отдельное консольное окно Windows и перенаправляет в него `stdin`/`stdout`/`stderr` на время интерактивной сессии `pdb`, не затрагивая собственные потоки ввода-вывода процесса `mebel.exe`. Команды `q`/`quit`, `c`/`continue` и Ctrl+C корректно завершают сессию отладчика и закрывают консольное окно, не завершая при этом процесс К3-Мебель. `q`/Ctrl+C, как и в обычном `pdb`, прерывают выполнение текущей операции через `bdb.BdbQuit`, но трейсбек этого исключения в консоли К3-Мебель заменяется коротким сообщением.

Для подключения текущего модуля к глобальному вызову breakpoint (начиная с версии Python 3.7) возможно использовать 2 способа:

- Установить значение переменной окружения PYTHONBREAKPOINT

```python
from __future__ import annotations

from k3_pdb_debugger import set_trace

set PYTHONBREAKPOINT=set_trace
```

> Пакет `k3_pdb_debugger` должен находиться в области видимости `sys.path`

- Перехватить вызов `sys.breakpointhook` глобально

```python
from __future__ import annotations

import sys
from k3_pdb_debugger import set_trace

sys.breakpointhook = set_trace
```

> Пример использования:

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

`set_trace` из пакета `k3_pdb_debugger` можно также использовать как декоратор с именованным аргументом `enable`: если `enable` равен `True`, сессия `pdb` запускается сразу при входе в декорируемую функцию; если `False` — функция вызывается как обычно, без отладки:

```python
from __future__ import annotations

from k3_pdb_debugger import set_trace

@set_trace(enable=True)  # отладка запускается
def function(a: int | float, b: int | float) -> int | float:
    ...

@set_trace(enable=False)  # отладка не запускается
def function(a: int | float, b: int | float) -> int | float:
    ...
```

## Основные функции

- `set_trace` - запуск процесса отладки
- `breakpoint` - алиас для `set_trace`, переопределяет стандартный `breakpoint`

## Зависимости

### Зависимости проекта

Пакет `k3_pdb_debugger` использует только компоненты стандартной библиотеки Python версии 3.7, а также `WinAPI` для взаимодействия с `cmd`.

### Зависимости, используемые в процессе разработки

- Python package manager [uv](https://docs.astral.sh/uv/)
- Python linter [ruff](https://docs.astral.sh/ruff/)
- Python type checker [mypy](https://github.com/python/mypy)
- Python unit testing framework [unittest](https://docs.python.org/3/library/unittest.html)
- Runner [make](https://www.gnu.org/software/make/) - [версия для Windows](https://gnuwin32.sourceforge.net/packages/make.htm)

> Также для проверки качества кода использовуются следующие пакеты:
>
> - Проверка покрытия кода тестами - [coverage](https://pypi.org/project/coverage/)
> - Проверка перед отправкой кода в git репозиторий - [pre-commit](https://pre-commit.com/)
> - Проверка сообщений commit на соответствие Conventional Commits - [commitizen](https://commitizen-tools.github.io/commitizen/)
> - Сборка сайта документации - [MyST Markdown](https://mystmd.org)

## Тестирование функциональности

В проекте представлены различные способы тестирования, для каждого из которых присутствует цель Make:

- Запуск unit-тестов и проверка покрытия кода unit-тестами - `make coverage`
- Только запуск unit-тестов - `make tests-all`
- Запуск конкретного модуля unit-теста - `make test-file путь_к_файлу_теста`
- Запуск End-to-end (E2E) тестов - `make e2e`
- Запуск проверок кодовой базы на соответствие требованиям линтера `ruff` - `make lint-all`
- Запуск проверок отдельного модуля на соответствие требованиям линтера `ruff` - `make lint-file путь_к_модулю`
- Запуск проверок кодовой базы на соответствие требованиям статического анализатора типов `mypy` - `make typing-all`
- Запуск проверок отдельного модуля на соответствие требованиям статического анализатора типов `mypy` - `make typing-file путь_к_файлу`

> Также доступна цель Make для запуска полного набора проверок:
>
> ```shell
> make check-all
> ```
