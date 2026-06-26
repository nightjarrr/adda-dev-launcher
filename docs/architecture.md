# adda-dev-launcher — Architecture Design

## Tech stack

| Role | Choice | Notes |
|---|---|---|
| Language | Python | Ecosystem solves distribution, CLI, config, keyring, testing — no custom infra |
| Distribution | `uv tool install <wheel-url>` from GitHub Releases | Modelled after molim; uv manages Python runtime — only host prerequisite is uv |
| Packaging | `pyproject.toml` + uv; hatch-vcs | Standard Python packaging; modelled after molim; version stamped from git tags |
| CLI framework | Typer | Built on Click; typed-function API; integrates with Rich; FastAPI org, well-maintained |
| Terminal output | Rich | Industry standard; used by pip, pytest, AWS CLI; same team as Textual |
| Interactive prompts | Textual | Rich-based TUI framework; same team as Rich; not required for MVP |
| Config files | `tomlkit` | read + write; validated by Pydantic v2 |
| Keyring | `keyring` + `jeepney` | `jeepney` = pure Python DBus; no native compilation; wheel stays `py3-none-any` |
| Subprocess / process | `stdlib` | `os.execvp` for process replacement; `subprocess.Popen` for `docker run -it`; SIGWINCH forwarding |
| Terminal multiplexer | `tmux -L <name>` | Dedicated tmux server; fully isolated from user's personal tmux sessions |
| Container engine | TBD | Docker and Podman both supported; detection/config mechanism TBD |
