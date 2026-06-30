# Coding Conventions

PEP 8 is the base style. This document lists all points where the codebase intentionally deviates from PEP 8, then covers project-specific conventions that PEP 8 does not address. Apply PEP 8 for anything not listed here.

---

## Status of these conventions

These conventions are required for all Python code.

When working on a feature or bug fix, do not perform broad unrelated cleanup unless the implementation plan explicitly includes it.

When this document conflicts with existing code, treat this document as the intended direction for future work.

---

## Scope

These conventions apply to Python source code under `src/adda_dev/` and tests under `tests/`.

`adda-dev` is a Linux-only CLI tool. Do not add portability abstractions for unsupported platforms.

---

## PEP 8 deviations

### Line length: 128 characters

Maximum line length is 128 characters (PEP 8: 79). Configured in `pyproject.toml` and enforced by Ruff.

---

## Naming

Follow PEP 8 naming conventions, enforced by Ruff (`N` rule set):

| Kind | Convention | Example |
|---|---|---|
| Classes | `PascalCase` | `ContainerConfig`, `EnvFile` |
| Functions, methods, variables | `snake_case` | `resolve_token`, `issue_id` |
| Constants | `SCREAMING_SNAKE_CASE` | `DEFAULT_IMAGE`, `ENV_FILE_NAME` |
| Private attributes and module-level internals | `_single_underscore` | `self._config`, `_load_env` |

---

## Type annotations

Annotate all function and method signatures — parameters and return types. Use Python 3.14 built-in generics (`list[str]`, `tuple[str, int]`). Do not use `typing.List`, `typing.Tuple`, or other deprecated aliases.

For generic functions and classes, use PEP 695 type-parameter syntax — `def load_toml[T: BaseModel](...) -> T`, `class Box[T]` — not `typing.TypeVar`/`typing.Generic` (Ruff `UP046`/`UP047` flag the legacy form on the 3.14 target).

---

## General rules

- **Filesystem paths:** use `pathlib.Path` throughout application logic. Convert incoming string paths at the boundary.

---

## Modules and packages

One module per functional area. When adding new functionality, decide first whether it belongs in an existing module or warrants a new one — do not let `cli.py` grow into a catch-all implementation file.

Promote a module to a sub-package when any of these apply:
- The module exceeds ~300 lines and contains multiple unrelated classes or concerns.
- Functionality is large enough to be independently testable as a group.

Sub-packages live under `src/adda_dev/`. Each subcommand that grows beyond a stub should have its own module or sub-package.

---

## Imports

Import grouping follows Ruff/isort: standard library, then third-party packages, then local package imports.

Within the package, use relative imports:

```python
from . import config, credentials
from .config import EnvFile
```

Import from the module that owns the concept. Avoid broad dependency reach-through.

---

## CLI conventions

The CLI is built with Typer. Follow these rules when adding or modifying commands.

**App structure.** The root `app` in `cli.py` must always have `no_args_is_help=True` and a `@app.callback()` function. Without the callback, Typer promotes a single subcommand to the root, collapsing the subcommand surface.

**One subcommand per module.** Each `@app.command()` function is a thin entry point: parse arguments, delegate to a module-level function, return. Do not put logic in the command function itself.

**Argument and option naming.** Use kebab-case for all CLI flags: `--issue-id`, `--dry-run`, `--no-cache`. Typer converts these to snake_case parameters automatically.

**Help text.** Every `@app.command()` and `@app.callback()` must have a docstring — Typer uses it as the CLI help text. Keep it short: one sentence describing what the command does.

**Adding a subcommand:**

1. Create a module in `src/adda_dev/` for the subcommand's implementation.
2. Add the `@app.command()` entry point in `cli.py`, delegating to the new module.
3. Add tests in `tests/test_{module}.py`.

---

## Output

`Output` is a `typing.Protocol` port defined in `common.py`. It exposes three methods: `info(message: str)`, `warning(message: str)`, and `error(exc: Exception)`. The production adapter is `RichOutput` in `infra/output.py`, which emits Rich-formatted terminal output.

- **Receive `Output` as a parameter and call its methods** — `output.info(...)`, `output.warning(...)`, `output.error(...)`. Do not import or instantiate `RichOutput` from `app/` or `domain/`.
- **Rich is an `infra/`-only library.** `RichOutput` wraps it; any other Rich-specific features (progress bars, tables, live displays) also belong in `infra/` adapters. `app/` and `domain/` must not import `rich` directly.
- **In tests, use `FakeOutput` from `tests/conftest.py`** — it captures calls in `info_calls`, `warning_calls`, and `error_calls` lists for assertion.
- **Do not use `print()`** in application code.

Raise `typer.Exit(code=1)` for fatal errors rather than calling `sys.exit()` directly.

---

## Tooling

Use `uv` for all Python work — environment, dependencies, build, and running project commands. Daily operations:

```bash
uv run pytest                     # run tests
uv run ruff format src/ tests/    # format
uv run ruff check src/ tests/     # lint
uv run mypy src/                  # type-check
uv run adda-dev                   # invoke the CLI
uv build                          # build wheel
/usr/local/libexec/adda-dev-runtime/bin/quality-gates  # run all local quality gates
```

Provision dependencies with `uv sync --frozen` — installs the pinned set from `uv.lock`. Run when `uv.lock` changes. Add new dependencies with `uv add` (runtime) or `uv add --group dev` (dev).

Do not use `pip`, `poetry`, or `uv pip`. Do not manually activate or deactivate the project virtualenv.

---

## Dependencies

Do not add runtime, development, or system dependencies unless the implementation plan explicitly calls for them. If the implementation appears to require a new dependency, escalate to the Project Owner via PM rather than adding it opportunistically.

---

## Comments

Write inline comments only when the *why* is non-obvious: a hidden constraint, a subtle invariant, or a workaround. Do not describe what the code does. One line per comment block.

Organise methods in a class into sections with a comment header when the class contains multiple well-defined groups:

```python
# Private methods

# Public methods
```

---

## Docstrings

**Module docstrings** use the multi-line header format:

```python
"""
adda-dev CLI entry point.
"""
```

**Class docstrings** — write one for abstract base classes and for classes whose contract is non-obvious from the name alone.

**Method and function docstrings** — write one when the expected behaviour requires explanation. Typer uses command function docstrings as CLI help text; always provide one for `@app.command()` and `@app.callback()` functions. No docstring is required for simple methods whose name makes the behaviour obvious.

---

## Testing

- Test files: `test_{module}.py` (e.g., `test_cli.py`, `test_config.py`).
- Test functions: `test_{subject}_{description}` where `subject` identifies the class or module-level function under test and `description` is a free label — a section keyword (`input_validation`, `core_logic`) or a specific scenario. Test function names must be all-lowercase `snake_case` (Ruff `N802` rejects any other case); lowercase a PascalCase class name into the `subject` segment — e.g. `test_project_file_valid_minimal` for `ProjectFile`, not `test_ProjectFile_valid_minimal`.
- Use `tmp_path` (function-scoped) and `tmp_path_factory` (module-scoped) for temporary filesystem state. Pytest cleans up both automatically. Do not create test state outside these fixtures without an explicit teardown.
- Static test data goes in `tests/data/{module}/` — create the folder only when the module's tests need static files.
- Shared fixtures used across multiple test modules go in `tests/conftest.py`.

Every new behaviour requires tests. Every bug fix requires a regression test.

**Coverage floor: 95%.** Enforced by pytest-cov — `uv run pytest` fails if combined line and branch coverage drops below this threshold.

---

## Bash

- Open with `#!/bin/bash` and `set -euo pipefail`.
- Begin each script with a brief comment block stating purpose, inputs, and outputs.
- Structure logic into named functions; group related functions under `# ---`-delimited section headings.
- `# shellcheck disable=SC…` requires a `# Why:` comment on the immediately following line.

### Style

- Prefer `[[ … ]]` over `[ … ]` for conditionals.
- Quote all variable expansions: `"${var}"`.
- Use `local` for variables inside functions.
- Prefer `printf` over `echo` for output that must be portable or include escape sequences.
- Keep functions short and single-purpose.

---

## Keeping this document current

When a convention changes, update this document in the same commit as the code or configuration that establishes the new convention.
