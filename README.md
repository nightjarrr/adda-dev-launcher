# adda-dev-launcher

[![Github Release](https://img.shields.io/github/v/release/nightjarrr/adda-dev-launcher)](https://github.com/nightjarrr/adda-dev-launcher/releases/latest)
[![CI](https://github.com/nightjarrr/adda-dev-launcher/actions/workflows/ci.yml/badge.svg)](https://github.com/nightjarrr/adda-dev-launcher/actions/workflows/ci.yml)
[![Release](https://github.com/nightjarrr/adda-dev-launcher/actions/workflows/release.yml/badge.svg)](https://github.com/nightjarrr/adda-dev-launcher/actions/workflows/release.yml)

Host-side launcher for the [ADDA Dev Runtime](https://github.com/nightjarrr/adda-dev-runtime) — an isolated, ephemeral, hardened container environment for AI agentic development projects following the ADDA SDLC.

---

## Requirements

Linux only, tested on Ubuntu 24.04.

| Tool | Purpose |
|---|---|
| `uv` | Installs and updates the `adda-dev` CLI. Manages its own Python interpreter — Python is not separately required. |
| Docker Engine | Runs the AI harness container and Envoy sidecar. Docker Desktop is not required. |
| `tmux` | Provides survivable terminal sessions. |
| `libsecret-tools` (`secret-tool`) | Retrieves credentials from the host keyring at launch time. |
| `seahorse` | Optional but recommended for GUI keyring inspection. |
| Ghostty (or another terminal emulator) | Hosts the tmux session. |
| Active GNOME / KDE / compatible Secret Service session | Required for the keyring to be unlocked at launch time. |

---

## Installation

Install or update to the latest release (requires `jq`):

```bash
sudo apt install jq
```

```bash
uv tool install --reinstall \
  $(curl -s https://api.github.com/repos/nightjarrr/adda-dev-launcher/releases/latest \
    | jq -r '.assets[] | select(.name | endswith(".whl")) | .browser_download_url')
```

To install a specific version, replace `<VERSION>` (e.g. `0.1.0`):

```bash
uv tool install --reinstall \
  https://github.com/nightjarrr/adda-dev-launcher/releases/download/v<VERSION>/adda_dev-<VERSION>-py3-none-any.whl
```

All available releases are listed on the [Releases page](https://github.com/nightjarrr/adda-dev-launcher/releases).

---

## Setup

### 1. Create a project file

Create `~/.config/adda-dev/projects/<name>.toml`:

```toml
image = "ghcr.io/<owner>/<repo>:<tag>"
provider = "anthropic"   # or "deepseek"

[github]
owner = "<owner>"
repo = "<repo>"
secret_name = "<repo>-token"   # used as the keyring username
```

`~/.config/adda-dev/config.toml` is optional — all defaults work for most users. The most likely override is `container_engine = "podman"`.

### 2. Store the Claude Code OAuth token

Acquire the token using a throwaway container:

```bash
docker run --rm -it oven/bun:latest \
  sh -c "BUN_INSTALL=/usr/local bun install -g @anthropic-ai/claude-code && claude setup-token"
```

The container prints an authorization URL. Open it in a browser, authorize, and copy the authorization code back into the container. Claude Code exchanges it for an OAuth token and displays it. Store it in the keyring:

```bash
secret-tool store --label='Claude Code OAuth' \
  service adda-dev:anthropic username oauth
```

### 3. Store the GitHub token

Generate a fine-grained Personal Access Token in GitHub settings, scoped to the single repository, with these permissions:

| Permission | Access |
|---|---|
| Metadata | Read |
| Contents | Read & write |
| Issues | Read & write |
| Pull requests | Read & write |
| Workflows | Read & write |
| Actions | Read |

No account-level permissions. No administration, secrets, deployments, webhooks, or Pages access.

Store it in the keyring:

```bash
secret-tool store --label='GitHub Token (<repo>)' \
  service adda-dev:github username <secret_name>
```

Where `<secret_name>` matches the value set in the project file.

---

## Usage

```bash
adda-dev run <project>                       # Start a session
adda-dev run <project> --issue N             # Start on the branch for issue N
adda-dev run <project> --deepseek            # Use DeepSeek backend
adda-dev run <project> -- <cmd> [args...]    # Override container command
```

The launcher creates a named tmux session. If the terminal closes, reattach using the session name printed at startup.

**Useful tmux keys:**

| Key | Action |
|---|---|
| `Ctrl-b d` | Detach from session |
| `Ctrl-b [` | Enter copy/scroll mode |
| `Ctrl-b x` | Kill current pane |

With mouse mode enabled (set by the launcher's tmux config), hold `Shift` while dragging to select text for host clipboard copy.

To increase Ghostty's scrollback buffer, add to your Ghostty config:

```
scrollback-limit = 100000000
```

---

## Diagnostics

### Envoy proxy

The Envoy sidecar exposes an admin interface on `127.0.0.1:9901` inside its container. It is not published to any host port. Access it via `docker exec` — the Envoy image has no HTTP client tools, so use bash's built-in TCP support (HTTP/1.1 required):

```bash
docker exec adda-dev-envoy-<RUN_ID> bash -c \
  'exec 3<>/dev/tcp/127.0.0.1/9901
   printf "GET /ready HTTP/1.1\r\nHost: localhost\r\n\r\n" >&3
   cat <&3'
```

Replace `/ready` with `/stats`, `/listeners`, `/clusters`, or `/config_dump` for other diagnostic endpoints. The `RUN_ID` is printed by the launcher at startup.

---

## Documentation

| Document | Contents |
|---|---|
| [`docs/conceptual-design.md`](docs/conceptual-design.md) | Conceptual model: design goals, threat model, architecture |
| [`docs/technical-design.md`](docs/technical-design.md) | Implementation reference: launcher sequence, authentication, networking |
| [`docs/architecture.md`](docs/architecture.md) | Python package architecture: design principles, module layout, configuration model |
| [`docs/launcher-container-contract.md`](docs/launcher-container-contract.md) | Launcher–container interface specification |
| [`docs/conventions.md`](docs/conventions.md) | Python coding conventions for this repo |

---

## Notes

- **Linux only.** Ubuntu 24.04 is the tested platform. No plans to support other platforms.
- **Ephemeral by design.** The container has no persistent storage. Push commits to GitHub before ending a session — anything not pushed is lost.
- **Personal project.** Features and design reflect personal workflows. PRs from external contributors are not being accepted. Feel free to fork and adapt.
- **Legacy Bash launcher.** A tarball of the `launcher/` directory is attached to each release for reference. The Bash launcher (`launcher/adda-dev.sh`) is no longer the active launcher and is pending removal.

---

## License

MIT — see [LICENSE](LICENSE) for details.
