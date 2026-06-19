# adda-dev-launcher

[![CI](https://github.com/nightjarrr/adda-dev-launcher/actions/workflows/ci.yml/badge.svg)](https://github.com/nightjarrr/adda-dev-launcher/actions/workflows/ci.yml)

Host-side launcher for the [ADDA Dev Runtime](https://github.com/nightjarrr/adda-dev-runtime) — an isolated, ephemeral, hardened container environment for AI agentic development projects following the ADDA SDLC.

**Status:** SDLC scaffolding in place. The launcher script and its companion templates are being imported from `adda-dev-runtime` in issue #404 and are not yet present in this repository.

## About

The launcher runs on the host machine (outside any container). It reads `adda-dev.env`, fetches keyring tokens, and starts the ADDA Dev Runtime container with the correct configuration.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines and [SECURITY.md](SECURITY.md) to report vulnerabilities.

This project follows the [ADDA SDLC](https://github.com/nightjarrr/adda-dev-runtime/blob/main/docs/adda-project-onboarding.md). Coding conventions are in [docs/conventions.md](docs/conventions.md).
