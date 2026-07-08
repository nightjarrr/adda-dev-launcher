# adda-dev-launcher — Technical Design

This document is the technical complement to [`docs/conceptual-design.md`](conceptual-design.md). It describes the concrete host-side implementation — launcher startup sequence, configuration variables, Envoy sidecar, network enforcement, and authentication.

**Audience: human Project Owner only.** Read when setting up, extending, or debugging the launcher or network policy. Not part of any agent's runtime context.

For the contract between the launcher and the container it starts, see [`docs/launcher-container-contract.md`](launcher-container-contract.md).

For the container-internal implementation — entrypoint sequence, bootstrap extension points, image build pipeline — see [`docs/adda-dev-runtime-technical-design.md`](https://github.com/nightjarrr/adda-dev-runtime/blob/main/docs/adda-dev-runtime-technical-design.md) in adda-dev-runtime.

Throughout, `{owner}` and `{repo}` refer to the GitHub namespace and repository name of the project.

---

## Technology stack

This section maps the technology-agnostic concepts from the conceptual design to the specific host-side technologies used in this implementation.

| Concept | Technology |
|---|---|
| AI harness container | Docker Engine |
| Network proxy sidecar | Envoy |
| Host terminal multiplexer | tmux |
| Host terminal emulator | Ghostty |
| Host secret storage | Secret Service (`secret-tool` / GNOME Keyring) |

---

## Host prerequisites

Linux only, tested on Ubuntu 24.04.

Required:

* `uv` — required to install and update the `adda-dev` CLI. Manages the Python interpreter; Python is not separately required.
* Docker Engine or compatible OCI runtime. Desktop is not required.
* `tmux` — used for survivable terminal sessions.
* An active GNOME, KDE, or compatible Secret Service login session, so the keyring is unlocked. The launcher retrieves credentials via the Python `keyring` library over D-Bus — no `secret-tool` binary is needed at runtime.
* `seahorse` — optional but recommended for GUI keyring inspection.
* A terminal emulator (Ghostty recommended).

Notably **not** required on the host: `git`, `gh`, the AI harness CLI, Python, Node, or any project-specific runtime tooling. Those live inside containers.

---

## Launcher

The `adda-dev` Python CLI (`adda-dev run <project>`). Creates one ephemeral AI harness dev runtime per invocation.

Invocation:

```bash
adda-dev run <project>
adda-dev run <project> --issue N
adda-dev run <project> --deepseek
adda-dev run <project> -- <cmd> [args...]
```

### Configuration

Two TOML file locations are used:

- **Host config** (optional): `~/.config/adda-dev/config.toml` — global overrides such as `container_engine`. All defaults work for most users without this file.
- **Project files**: `~/.config/adda-dev/projects/<name>.toml` — one file per project.

Project file schema:

```toml
image = "ghcr.io/<owner>/<repo>:<tag>"
provider = "anthropic"   # or "deepseek"

[github]
owner = "<owner>"
repo = "<repo>"
secret_name = "<repo>-token"   # used as the keyring username
```

### Behavior

1. Validate arguments.
2. Verify host prerequisites: `docker`, `secret-tool`, `tmux`.
3. Load the project TOML file for `<project>` from `~/.config/adda-dev/projects/<project>.toml` and validate it.
4. Seed `~/.tmux.conf` from `scripts/adda-dev.tmux.conf` only if missing; source it best-effort.
5. If not already inside tmux, generate a session name, export it, and re-enter the launcher inside a named tmux session.
6. Retrieve auth tokens from the Secret Service keyring. See *Authentication*.
7. Detect host timezone.
8. Create a private per-run runtime directory under `${XDG_RUNTIME_DIR:-/tmp}`.
9. Render Envoy config from `envoy.yaml.template`, co-located with the launcher script, into the runtime directory.
10. Start Envoy sidecar container with hardened flags. See *Envoy sidecar*.
11. Wait for the Envoy Unix socket.
12. Create `adda-dev shell` and `adda-dev envoy logs` windows in the primary tmux session. The `adda-dev shell` window invokes `open-interactive-shell.sh` in the container via `docker exec`, which polls for `/run/.adda_bootstrap_complete` before opening the interactive bash prompt. The container entrypoint guarantees the marker is written in both success and failure scenarios. If `open-interactive-shell.sh` is absent in the container, the interactive shell window fails to open; the main session is unaffected.
13. Assemble and run the AI harness container. See *Launcher contract* for flags and environment.
14. On exit, stop Envoy and remove the runtime directory.

### tmux and terminal emulator

The launcher creates a named host tmux session and re-enters itself inside that session. This keeps the launcher, Envoy lifecycle, and `docker run` under tmux control. If the terminal emulator crashes or closes, the tmux server keeps the session alive. Reattach using the printed tmux session name.

The launcher seeds `~/.tmux.conf` from `scripts/adda-dev.tmux.conf` only when `~/.tmux.conf` is absent. Existing user tmux config is never overwritten.

### Concurrency

Multiple features may run concurrently. Each invocation gets its own AI harness container, Envoy sidecar, runtime directory, Unix socket, and tmux session. Sessions share no state with each other except through GitHub.

### Legacy Bash launcher

`launcher/adda-dev.sh` was the original host-side launcher. It is preserved in the repository for reference and is pending removal.

---

## Envoy sidecar

Runs as a separate container managed by the launcher. Not inside the AI harness container. Per-session: one AI harness container gets one Envoy sidecar.

The Envoy sidecar is outside the AI harness container trust boundary but should still be minimized. Hardening flags:

* exact image version and digest pinned in launcher configuration
* `--rm -d`
* `--cap-drop ALL`
* `--security-opt no-new-privileges`
* read-only root where compatible
* tmpfs for `/tmp`
* admin interface not published to host; accessible via `docker exec` only

See *Network* for Envoy's policy responsibilities.

### Admin interface

Bound to container loopback (`127.0.0.1:9901`). Not published to any host port — parallel Envoy sidecars coexist without port conflicts.

The admin interface is for diagnostics only. It is not a policy editing UI and must not be exposed to untrusted networks.

---

## Network

This section describes Envoy sidecar network policy. The `--network none` isolation flag is described in *Launcher contract §1.3 Hardening*. The in-container proxy bridge started by the entrypoint is described in the adda-dev-runtime technical design.

### Envoy policy

Envoy responsibilities:
* Accept explicit HTTP proxy traffic on the Unix socket.
* Support plain HTTP forwarding and HTTPS `CONNECT` tunneling.
* Enforce domain allow-list / default-deny policy using RBAC.
* Resolve allowed upstream domains.
* Emit access logs for audit/debugging.

Default-deny is achieved via Envoy RBAC `action: ALLOW` — no explicit wildcard deny rule is needed; a request that matches no policy entry is denied automatically.

Policy match basis is `:authority`. For HTTPS `CONNECT`, authority is `host:port` (e.g. `api.github.com:443`); for plain HTTP, authority may be `host` or `host:port` — allow-list entries must account for both forms.

For HTTPS destinations, clients send HTTP `CONNECT` to Envoy. Envoy sees the target authority (e.g. `api.github.com:443`) but does not decrypt TLS in the baseline design.

### DNS

Envoy receives the requested authority from the explicit proxy request and resolves allowed destinations from the sidecar container. Policy is applied before DNS resolution and before upstream connection.

### Allow-list

Target-state allow-list is default-deny. Requests are allowed only if the requested authority matches an explicit policy.

Baseline target destinations:

| Destination | Why |
|---|---|
| `api.anthropic.com` | Claude Code API calls. |
| `claude.ai` | Claude Code auth/runtime flows where required. |
| `statsig.anthropic.com` | Claude Code telemetry / feature gates, if required. |
| `sentry.io` | Claude Code error reporting, if required. |
| `github.com` | Git over HTTPS, web endpoint dependencies. |
| `api.github.com` | GitHub CLI issue, PR, label, branch linkage, and account API calls. |
| `raw.githubusercontent.com` | Raw repository content where required. |
| `objects.githubusercontent.com` | GitHub release assets and Git LFS objects where required. |
| narrowly scoped `githubusercontent.com` hosts | GitHub-hosted raw/assets content where required. |

Runtime package-registry access:
- Container/toolchain dependencies are baked into the image and do not require runtime package-manager access.
- Project code dependencies may require runtime registry access. Registry access must be explicit, ecosystem-specific, and lockfile/frozen-mode based. Examples: PyPI domains for Python/uv projects; npm registry domains for Node projects.
- OS package registries such as APT mirrors are not allowed in the runtime container.
- `ghcr.io` is not required inside the container; the host launcher pulls the image.

### Failure handling

Target-state behavior:
* If Envoy cannot start, the launcher fails before starting the AI harness container.
* If the Unix socket does not appear, the launcher fails.
* If a request does not match the allow-list, Envoy denies it.
* If a process bypasses proxy configuration, it has no network path due to `--network none`.

### Broad web research / Web Fetch

Direct URL fetching and broad internet research conflict with a narrow runtime allow-list. The baseline design does not open general internet egress for this use case. Future design work will define a separate retrieval plane.

---

## Authentication

Authentication spans the launcher (credential retrieval and injection) and the entrypoint (credential use and cleanup). The entrypoint's side — GitHub authentication initialization and removal of the token from the process environment — is described in the adda-dev-runtime technical design. This section covers the host-side credential lifecycle.

### Secrets

Two authentication secrets are required:
* **AI harness credential** — either a Claude Code OAuth token (Anthropic provider) or a DeepSeek API key (DeepSeek provider).
* **GitHub Token** — for repository access.

Both are stored in the host Secret Service keyring, retrieved by the launcher, and injected into the container at startup.

### Secret naming in keyring

| Secret | Service | Username |
|---|---|---|
| Claude Code OAuth token | `adda-dev:anthropic` | `oauth` (default; override via `[llm.anthropic] secret_name` in `config.toml`) |
| GitHub Token | `adda-dev:github` | `secret_name` from the project file |
| DeepSeek API key | `adda-dev:deepseek` | `apikey` (default; override via `[llm.deepseek] secret_name` in `config.toml`) |

Each entry uses a namespaced service name (`adda-dev:<system>`) and a `username` attribute. The GitHub username is the `secret_name` value from the project TOML file, allowing multiple repos to coexist in one keyring by using distinct values (e.g. `acme-token`, `otherrepo-token`).

### Retrieval

The launcher retrieves credentials at runtime using the Python `keyring` library, which accesses the host Secret Service directly over D-Bus. No `secret-tool` binary is invoked. If a credential is not found, the launcher fails fast with an error identifying the missing entry.

To verify stored entries manually:

```bash
secret-tool lookup service adda-dev:anthropic username oauth
secret-tool lookup service adda-dev:github username <secret_name>
```

### Rotation

Re-run the bootstrap or GitHub token generation procedure and store a replacement value using the same `secret-tool store` attributes. Recommended GitHub Token rotation interval: 90 days or less.

### GitHub Token scoping

Hard requirements:
* Repository scope: exactly one repository, `{owner}/{repo}`.
* No account-level permissions.
* No repository administration permissions.
* No access to secrets, variables, environments, deployments, webhooks, Pages, Codespaces, or repository settings.

Baseline repository permissions:

| Permission | Access | Why |
|---|---|---|
| Metadata | Read | Prerequisite for everything else. |
| Contents | Read & write | Clone, fetch, push, branch creation/deletion. |
| Issues | Read & write | Issue creation, labels, comments, phase tracking. |
| Pull requests | Read & write | PR creation, comments, review/status updates. |
| Workflows | Read & write | Required if SDLC-governed work modifies `.github/workflows/*`. |
| Actions | Read | Read CI status and quality-gate results. |

Grey-area permissions are added only when a named SDLC operation requires them and the reason is documented in the repository.

---

## Launcher contract

This section describes how the launcher satisfies its §1 obligations under the [launcher–container contract](launcher-container-contract.md). The contract specifies what the container checks and at what enforcement level; what follows is how the launcher produces it.

### §1.1 Environment

| Contract variable | Source |
|---|---|
| `GITHUB_OWNER` | `adda-dev.env` |
| `GITHUB_REPO` | `adda-dev.env` |
| `GITHUB_TOKEN_` | Keyring — see *Authentication* |
| `TZ` | Detected at runtime (step 7) |
| `ADDA_DEV_PROXY_SOCKET` | `adda-dev.env`: `ADDA_DEV_PROXY_SOCKET_CONTAINER_PATH` |
| `ADDA_DEV_PROXY_PORT` | `adda-dev.env` |
| `ADDA_DEV_LLM_BACKEND` | `adda-dev.env` |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | Hardcoded to `1` |
| `ADDA_DEV_RUNTIME_IMAGE` | Optional; `adda-dev.env` |
| `ISSUE_ID` | Optional; command-line argument |
| `CLAUDE_CODE_OAUTH_TOKEN` | Keyring — Anthropic provider; see *Authentication* |
| `ANTHROPIC_BASE_URL` | DeepSeek provider; `adda-dev.env` |
| `ANTHROPIC_AUTH_TOKEN` | DeepSeek provider; keyring — see *Authentication* |
| `ANTHROPIC_MODEL` | DeepSeek provider; `adda-dev.env` |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | DeepSeek provider; `adda-dev.env` |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | DeepSeek provider; `adda-dev.env` |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | DeepSeek provider; `adda-dev.env` |
| `CLAUDE_CODE_SUBAGENT_MODEL` | DeepSeek provider; `adda-dev.env` |
| `CLAUDE_CODE_EFFORT_LEVEL` | DeepSeek provider; `adda-dev.env` |

Provider credentials are selected by `ADDA_DEV_LLM_BACKEND`: `CLAUDE_CODE_OAUTH_TOKEN` for the Anthropic provider; the eight `ANTHROPIC_*` and `CLAUDE_CODE_*` variables above for the DeepSeek provider.

### §1.2 Filesystem

All tmpfs mounts include `uid=${ADDA_DEV_UID},gid=${ADDA_DEV_GID}` mount options (default `1000:1000`); this is how the container runtime user owns the writable paths. The launcher does not pass `--user` for the AI harness container — the image's `USER` directive sets the process user.

| Mount | Launcher implementation |
|---|---|
| `/home/${ADDA_DEV_USER}` | tmpfs, mode `0700`, exec; size: `ADDA_DEV_HOME_TMPFS_SIZE` (default `512m`) |
| `/workspace` | tmpfs, mode `0700`, exec; size: `ADDA_DEV_WORKSPACE_TMPFS_SIZE` (default `256m`) |
| `/tmp` | tmpfs, mode `0700`, exec; size: `ADDA_DEV_TMP_TMPFS_SIZE` (default `256m`) |
| `/run` | tmpfs, mode `0700`, noexec; hardcoded `32m` |
| Proxy socket (`ADDA_DEV_PROXY_SOCKET`) | Bind-mounted as an immediate child of `/run` (e.g. `/run/proxy.sock`), avoiding nested parent directories under the `/run` tmpfs. Socket permissions must allow the container runtime user to connect despite possible UID/GID mismatch between host user, Envoy sidecar process, and container user. |

Tmpfs sizes are limits, not pre-allocated RAM reservations. Docker also provides managed files (`/etc/hosts`, `/etc/hostname`, `/etc/resolv.conf`) as expected runtime configuration; these do not provide network access.

### §1.3 Hardening

The AI harness container is launched with the following `docker run` flags:

| Flag | Effect |
|---|---|
| `--cap-drop ALL` | No effective capabilities; network enforcement stays outside the container via the sidecar. |
| `--security-opt no-new-privileges` | No privilege escalation via setuid or setgid binaries. |
| `--read-only` | Root filesystem read-only; writable paths are the explicit tmpfs mounts in §1.2. |
| `--network none` | No network interfaces except loopback; all outbound traffic must route through the sidecar proxy socket. |
