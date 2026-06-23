# adda-dev-launcher — Architecture Decisions

## Tech stack

Covers the launcher rewrite (issue #45).

| Role | Choice | Notes |
|---|---|---|
| Language | Python | Ecosystem solves distribution, CLI, config, keyring, testing — no custom infra |
| Distribution | `uv tool install <wheel-url>` from GitHub Releases | Modelled after molim; uv manages Python runtime — only host prerequisite is uv |
| Packaging | `pyproject.toml` + uv; hatch-vcs | Standard Python packaging; version stamped from git tags |
| CLI framework | Typer | Built on Click; typed-function API; integrates with Rich; FastAPI org, well-maintained |
| Terminal output | Rich | Industry standard; used by pip, pytest, AWS CLI; same team as Textual |
| Interactive prompts | TBD | questionary or Textual — to be decided during implementation design |
| Config files | `tomllib` | stdlib since Python 3.11; zero additional dependency |
| Keyring | `keyring` + `jeepney` | `jeepney` = pure Python DBus; no native compilation; wheel stays `py3-none-any` |
| Subprocess / process | `stdlib` + optional `sh` | `os.execvp` for process replacement; `subprocess.Popen` for `docker run -it`; SIGWINCH forwarding |
| Terminal multiplexer | `tmux -L adda` | Dedicated tmux server; fully isolated from user's personal tmux sessions |
| Container engine | TBD | Docker and Podman both supported; detection/config mechanism TBD |
