# adda-dev-launcher

This is the host-side launcher for the ADDA Dev Runtime. It runs on the host machine (outside any container) and is responsible for reading host and project configuration from `~/.config/adda-dev/`, fetching credentials from the OS keyring, and launching the ADDA Dev Runtime container via Docker.

## Project overview

The launcher is being redesigned in Python. The Bash script in `launcher/` remains the active launcher until the Python redesign is complete.

The Python package (`adda-dev`) is the active launcher. Its source lives in `src/adda_dev/`.

The `launcher/` directory contains the legacy Bash launcher (`adda-dev.sh`) and its companion templates. It is preserved for reference and is pending removal.

## Repo layout

```
src/adda_dev/            # Python package source
  __init__.py            # package root
  infra/cli.py           # Typer CLI entry point and composition root
  data/                  # bundled data files
    envoy.yaml.template  # Envoy proxy sidecar template (copied from launcher/)
    adda-dev.tmux.conf   # tmux session configuration (copied from launcher/)
tests/                   # pytest test suite
  conftest.py            # pytest configuration and shared test doubles
docs/                    # design and reference documentation
  architecture.md        # Python package architecture: principles, layout, config/project model
  conventions.md         # coding conventions for this repo
  launcher-container-contract.md  # authoritative host-container runtime contract
launcher/                # host-side Bash launcher (active until #52 is complete)
  adda-dev.sh            # launcher entry-point script
  adda-dev.env.example   # example environment configuration
  envoy.yaml.template    # Envoy proxy sidecar template
  adda-dev.tmux.conf     # tmux session configuration
pyproject.toml           # Python package config (build, deps, tool config)
uv.lock                  # locked dependency versions (committed)
.python-version          # pins Python 3.14 for uv
.adda-init.sh            # repo-level init hook (syncs deps, installs pre-commit hook)
.quality-gates.toml      # local quality gate definitions
```

## Toolchain

- **Shell:** Bash. All scripts use `#!/bin/bash` and `set -euo pipefail`.
- **Python:** Python >=3.14, managed by uv. Entry point: `adda-dev`.
- **Package manager:** uv. Sync deps: `uv sync`. Run tools: `uv run <tool>`.
- **Testing:** pytest. Run: `uv run pytest`.
- **Linting/formatting:** ruff. Run: `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/`.
- **Type checking:** mypy (strict). Run: `uv run mypy src/`.
- **Build:** `uv build` produces a wheel in `dist/`.
- **Pre-commit hooks:** managed by `pre-commit` (installed via `uv run pre-commit install`). Installed automatically by `.adda-init.sh`.
- **Local quality gate:** shell-syntax + python-lint + python-format + python-types + python-tests, via `.quality-gates.toml`. Run with `/usr/local/libexec/adda-dev-runtime/bin/quality-gates`.
- **CI quality gates:** `shellcheck` (lint), `gitleaks` (secret scan), and Python checks (ruff, mypy, pytest) — shell and secret gates run in CI only and are not available in the dev container.
- **Coverage:** pytest-cov; branch coverage configured in `pyproject.toml`. Reports: terminal (missing lines) + XML for CI.

## References

- `docs/architecture.md` — Python package architecture: design principles, module layout, and the config/project model.
- `docs/conventions.md` — coding conventions for this project.
- `docs/launcher-container-contract.md` — authoritative host-container contract.
