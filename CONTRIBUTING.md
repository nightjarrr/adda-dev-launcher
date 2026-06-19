# Contributing

This is a personal project developed for the author's own use. It is shared publicly in the hope it may be useful to others, but **pull requests from external contributors are not being accepted** at this time.

The project is licensed under the MIT license (see [LICENSE](LICENSE)). You are welcome to fork it and adapt it to your own needs.

## Bug reports and feature suggestions

Bug reports and feature suggestions are welcome via [GitHub Issues](https://github.com/nightjarrr/adda-dev-launcher/issues). Please understand that this is a single-author project and issues may not be addressed promptly.

## Forks

If you fork this project and make improvements, you are welcome to describe your changes via an issue for case-by-case consideration.

## Development setup

This repository is designed to be developed from inside the ADDA Dev Runtime. See the [README](README.md) for prerequisites and setup instructions.

**Local quality gate:** the repository uses `bash -n` syntax checking via `.quality-gates.toml`. The local gate runs only what is available in the dev container; it is the fast-feedback loop before committing.

**CI quality gates:** `shellcheck` and secret scanning (`gitleaks`) run in CI and are the authoritative check. These tools are not installed in the dev container — CI is where they run.

**Pre-commit quality gates:** the repository is configured with a pre-commit hook that runs all local quality gates before each commit. If a commit is blocked, address the reported issue, re-stage, and commit again. Run `.adda-init.sh` to install the hook.
