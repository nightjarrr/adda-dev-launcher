# adda-dev-launcher

[![CI](https://github.com/nightjarrr/adda-dev-launcher/actions/workflows/ci.yml/badge.svg)](https://github.com/nightjarrr/adda-dev-launcher/actions/workflows/ci.yml)

Host-side launcher for the [ADDA Dev Runtime](https://github.com/nightjarrr/adda-dev-runtime) — an isolated, ephemeral, hardened container environment for AI agentic development projects following the ADDA SDLC.

---

## Requirements

Linux only, tested on Ubuntu 24.04.

| Tool | Purpose |
|---|---|
| Docker Engine | Runs the AI harness container and Envoy sidecar. Docker Desktop is not required. |
| `tmux` | Provides survivable terminal sessions. |
| `bash` | Required by the launcher script. |
| `openssl` | Generates random run/session identifiers in the launcher. |
| `libsecret-tools` (`secret-tool`) | Retrieves credentials from the host keyring at launch time. |
| `seahorse` | Optional but recommended for GUI keyring inspection. |
| Ghostty (or another terminal emulator) | Hosts the tmux session. |
| Active GNOME / KDE / compatible Secret Service session | Required for the keyring to be unlocked at launch time. |

---

## Setup

### 1. Download the launcher

Download the latest launcher tarball from the [Releases page](https://github.com/nightjarrr/adda-dev-launcher/releases/latest) and extract it into a directory of your choice:

```bash
tar -xzf adda-dev-launcher-<version>.tar.gz
```

The tarball contains: `adda-dev.sh`, `adda-dev.env.example`, `adda-dev.tmux.conf`, and `envoy.yaml.template`.

> **Note:** Releases are not yet available — the launcher tarball lands in a future issue. Check back on the Releases page once that work is complete.

### 2. Configure the project

Copy `adda-dev.env.example` to `adda-dev.env` in the same directory and fill in your values:

```bash
# GitHub repo
GITHUB_OWNER=<owner>
GITHUB_REPO=<repo>

# Container image — full reference including tag or digest
ADDA_DEV_IMAGE=ghcr.io/<owner>/<repo>:<tag>
ADDA_DEV_USER=adda
ADDA_DEV_UID=1000
ADDA_DEV_GID=1000
ADDA_DEV_HOME_TMPFS_SIZE=512m
ADDA_DEV_WORKSPACE_TMPFS_SIZE=256m
ADDA_DEV_TMP_TMPFS_SIZE=256m

# LLM backend: anthropic or deepseek
ADDA_DEV_LLM_BACKEND=anthropic

# Keyring entry keys — each repo uses its own GitHub key to allow coexistence
ADDA_DEV_KEYRING_GITHUB_KEY=<repo>-token
ADDA_DEV_KEYRING_CLAUDE_KEY=oauth
ADDA_DEV_KEYRING_DEEPSEEK_KEY=apikey

ADDA_DEV_PROXY_SOCKET_CONTAINER_PATH=/run/proxy.sock
ADDA_DEV_PROXY_PORT=8080
ENVOY_IMAGE=envoyproxy/envoy:v1.33.14
ENVOY_SOCKET_CONTAINER_PATH=/run/adda-dev-proxy/proxy.sock
```

### 3. Store the Claude Code OAuth token

Acquire the token using a throwaway container:

```bash
docker run --rm -it oven/bun:latest \
  sh -c "BUN_INSTALL=/usr/local bun install -g @anthropic-ai/claude-code && claude setup-token"
```

The container prints an authorization URL. Open it in a browser, authorize, and copy the authorization code back into the container. Claude Code exchanges it for an OAuth token and displays it. Store it in the keyring:

```bash
secret-tool store --label='Claude Code OAuth' \
  service adda-dev account claude key oauth
```

### 4. Store the GitHub token

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
  service adda-dev account github key <repo>-token
```

Replace `<repo>-token` with the value you set in `ADDA_DEV_KEYRING_GITHUB_KEY`.

---

## Usage

```bash
adda-dev.sh                          # Start a session on main
adda-dev.sh <issue-id>               # Start on the branch linked to an issue
adda-dev.sh --deepseek <issue-id>    # Use DeepSeek backend
adda-dev.sh -- <cmd> [args...]       # Override container command (debugging)
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
| [`docs/launcher-container-contract.md`](docs/launcher-container-contract.md) | Launcher–container interface specification |
| [`docs/conventions.md`](docs/conventions.md) | Bash style conventions for this repo |

---

## Notes

- **Linux only.** Ubuntu 24.04 is the tested platform. No plans to support other platforms.
- **Ephemeral by design.** The container has no persistent storage. Push commits to GitHub before ending a session — anything not pushed is lost.
- **Personal project.** Features and design reflect personal workflows. PRs from external contributors are not being accepted. Feel free to fork and adapt.

---

## License

MIT — see [LICENSE](LICENSE) for details.
