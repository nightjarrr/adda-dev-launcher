#!/bin/bash
set -euo pipefail
# Repo-level init hook for adda-dev-launcher.
# Invoked as a subprocess by the entrypoint at bootstrap and by current-issue switch mid-session.
# Inputs:  pyproject.toml (Python deps synced via uv)
# Outputs: .git/hooks/pre-commit installed via pre-commit

uv sync --frozen
uv run pre-commit install
