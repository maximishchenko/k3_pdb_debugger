.PHONY: lint-all typing-all tests-all check-all \
        lint-file typing-file test-file check-file \
        pre-commit sync check-commit-msg coverage e2e

check-all: lint-all typing-all tests-all coverage

check-file: lint-file typing-file test-file coverage

lint-all:
	uv run ruff check .

typing-all:
	uv run --with mypy -- python -m mypy --strict .

tests-all:
	uv run python -m unittest discover -v -s tests/unit -t tests/unit/

lint-file:
	uv run ruff check --force-exclude $(FILE)

typing-file:
	uv run --with mypy -- python -m mypy --strict $(FILE)

test-file:
	uv run python -m unittest discover -v -s $(dir $(FILE)) -t tests/unit/ -p $(notdir $(FILE))

pre-commit:
	uv run python -m pre_commit run --all-files

example-breakpoint:
	uv run python -m examples.example_breakpoint

example-decorator:
	uv run python -m examples.example_decorator

check-commit-msg:
	uv run python -m commitizen check --commit-msg-file $(filter-out $@,$(MAKECMDGOALS))

coverage:
	uv run python -m coverage run -m unittest discover -s tests/unit -t tests/unit
	uv run python -m coverage report

# Требуют реального консольного окна процесса (не headless), но не
# требуют запущенного К3-Мебель — тесты сами пропускаются, если
# процесс не прикреплён к консоли.
e2e:
	uv run python -m unittest discover -v -s tests/e2e -t tests/e2e

%:
	@:

sync:
	uv sync
