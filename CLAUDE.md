# adda-dev-launcher

This is the host-side launcher for the ADDA Dev Runtime. It runs on the host machine (outside any container) and is responsible for reading `adda-dev.env`, fetching keyring tokens, and launching the ADDA Dev Runtime container via Docker.

## Project overview

The launcher is a Bash script that:
1. Reads `adda-dev.env` for project and runtime configuration.
2. Retrieves secrets from the host keyring.
3. Starts the ADDA Dev Runtime container with the correct mounts, environment, and network configuration.
4. Optionally starts an Envoy proxy sidecar (using `envoy.yaml.template`).

The launcher code and its companion templates live in the `launcher/` directory.

## Repo layout

```
launcher/                # host-side launcher files
  adda-dev.sh            # launcher entry-point script
  adda-dev.env.example   # example environment configuration
  envoy.yaml.template    # Envoy proxy sidecar template
  adda-dev.tmux.conf     # tmux session configuration
.adda-init.sh            # repo-level init hook (installs pre-commit hook)
.quality-gates.toml      # local quality gate definitions
docs/conventions.md      # coding conventions for this repo
```

## Toolchain

- **Shell:** Bash. All scripts use `#!/bin/bash` and `set -euo pipefail`.
- **Local quality gate:** `bash -n` syntax check on all `.sh` files, via `.quality-gates.toml`. Run with `/usr/local/libexec/adda-dev-runtime/bin/quality-gates`.
- **CI quality gates:** `shellcheck` (lint) and `gitleaks` (secret scan) — these run in CI only and are not available in the dev container.
- **Pre-commit hook:** installed by `.adda-init.sh`; runs the local quality gates before each commit.

## References

- `docs/conventions.md` — Bash style conventions for this project.
- `docs/launcher-container-contract.md` — authoritative host-container contract.
