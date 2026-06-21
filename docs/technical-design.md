# adda-dev-launcher — Technical Design

This document is the technical complement to [`docs/conceptual-design.md`](conceptual-design.md). It describes the concrete host-side implementation — launcher startup sequence, configuration variables, Envoy sidecar, network enforcement, and authentication.

**Audience: human Project Owner only.** Read when setting up, extending, or debugging the launcher or network policy. Not part of any agent's runtime context.

For the contract between the launcher and the container it starts, see [`docs/launcher-container-contract.md`](https://github.com/nightjarrr/adda-dev-runtime/blob/main/docs/launcher-container-contract.md).

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

* Docker Engine or compatible OCI runtime. Desktop is not required.
* Bash.
* `openssl` command-line utility — used by the launcher for random run/session identifiers.
* Ghostty, or another modern terminal emulator.
* `tmux` — used for survivable terminal sessions.
* `libsecret-tools` — provides `secret-tool` for keyring access.
* `seahorse` — optional but recommended for GUI keyring inspection.
* An active GNOME, KDE, or compatible Secret Service login session, so the keyring is unlocked.

Notably **not** required on the host: `git`, `gh`, the AI harness CLI, Python, Node, uv, or any project-specific runtime tooling. Those live inside containers.

---

## Launcher

Host-side script (`adda-dev.sh`). Creates one ephemeral AI harness dev runtime per invocation.

Invocation:

```bash
adda-dev.sh
adda-dev.sh <issue-id>
adda-dev.sh -- <cmd> [args...]
adda-dev.sh <issue-id> -- <cmd> [args...]
```

### Per-project configuration

The launcher reads `adda-dev.env` from the same directory as the launcher script.

Required variables:

```bash
# Github repo
GITHUB_OWNER=
GITHUB_REPO=

# ADDA Dev Runtime container image configuration
ADDA_DEV_IMAGE=
ADDA_DEV_USER=adda
ADDA_DEV_UID=1000
ADDA_DEV_GID=1000
ADDA_DEV_HOME_TMPFS_SIZE=500m
ADDA_DEV_WORKSPACE_TMPFS_SIZE=200m
# Needs to be a file directly in /run to support the /run tmpfs
ADDA_DEV_PROXY_SOCKET_CONTAINER_PATH=/run/proxy.sock
ADDA_DEV_PROXY_PORT=8080

# Envoy perimeter sidecar configuration
ENVOY_IMAGE=envoyproxy/envoy:v1.33.14
ENVOY_SOCKET_CONTAINER_PATH=/run/adda-dev-proxy/proxy.sock
```

### Behavior

1. Validate arguments.
2. Verify host prerequisites: `docker`, `secret-tool`, `tmux`, `openssl`.
3. Source `adda-dev.env` and validate required variables.
4. Seed `~/.tmux.conf` from `scripts/adda-dev.tmux.conf` only if missing; source it best-effort.
5. If not already inside tmux, generate a session name, export it, and re-enter the launcher inside a named tmux session.
6. Retrieve auth tokens from the Secret Service keyring. See *Authentication*.
7. Detect host timezone.
8. Create a private per-run runtime directory under `${XDG_RUNTIME_DIR:-/tmp}`.
9. Render Envoy config from `envoy.yaml.template`, co-located with the launcher script, into the runtime directory.
10. Start Envoy sidecar container with hardened flags. See *Envoy sidecar*.
11. Wait for the Envoy Unix socket.
12. Create `adda-dev shell` and `adda-dev envoy logs` windows in the primary tmux session. The `adda-dev shell` window invokes a container-side script that waits for bootstrap to finish before opening the interactive bash prompt.
13. Assemble and run the AI harness container. See *Filesystem and process hardening* for flags and *Network* for proxy wiring.
14. On exit, stop Envoy and remove the runtime directory.

### tmux and terminal emulator

The launcher creates a named host tmux session and re-enters itself inside that session. This keeps the launcher, Envoy lifecycle, and `docker run` under tmux control. If the terminal emulator crashes or closes, the tmux server keeps the session alive. Reattach using the printed tmux session name.

The launcher seeds `~/.tmux.conf` from `scripts/adda-dev.tmux.conf` only when `~/.tmux.conf` is absent. Existing user tmux config is never overwritten.

### Concurrency

Multiple features may run concurrently. Each invocation gets its own AI harness container, Envoy sidecar, runtime directory, Unix socket, and tmux session. Sessions share no state with each other except through GitHub.

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

The host-side network story spans the launcher (starts Envoy) and the Envoy sidecar (enforces policy). The in-container side — the `socat` proxy bridge started by the entrypoint and the proxy environment variables it exports — is described in [adda-dev-runtime technical design](https://github.com/nightjarrr/adda-dev-runtime/blob/main/docs/adda-dev-runtime-technical-design.md). This section covers the host-side setup and the full proxy picture needed to understand how the sidecar socket is used by the container.

### Container networking

The AI harness container is launched with `--network none`.

Expected properties inside the container:
* Only loopback is available.
* There is no default route.
* Direct DNS resolution to internet resolvers is unavailable.
* Direct TCP connections to internet IPs fail.
* Tools that ignore proxy settings fail to reach the network.

### Proxy bridge

Most applications understand HTTP proxies as `host:port`, not Unix sockets. The entrypoint starts a `socat` bridge inside the container:

```text
127.0.0.1:<ADDA_DEV_PROXY_PORT>  ->  <ADDA_DEV_PROXY_SOCKET>
```

The entrypoint then exports:

```bash
HTTP_PROXY=http://127.0.0.1:<port>
HTTPS_PROXY=http://127.0.0.1:<port>
http_proxy=http://127.0.0.1:<port>
https_proxy=http://127.0.0.1:<port>
NO_PROXY=localhost,127.0.0.1,::1
no_proxy=localhost,127.0.0.1,::1
```

For HTTPS destinations, clients send HTTP `CONNECT` to Envoy. Envoy sees the target authority (e.g. `api.github.com:443`) but does not decrypt TLS in the baseline design.

### Envoy policy

Envoy responsibilities:
* Accept explicit HTTP proxy traffic on the Unix socket.
* Support plain HTTP forwarding and HTTPS `CONNECT` tunneling.
* Enforce domain allow-list / default-deny policy using RBAC.
* Resolve allowed upstream domains.
* Emit access logs for audit/debugging.

Default-deny is achieved via Envoy RBAC `action: ALLOW` — no explicit wildcard deny rule is needed; a request that matches no policy entry is denied automatically.

Policy match basis is `:authority`. For HTTPS `CONNECT`, authority is `host:port` (e.g. `api.github.com:443`); for plain HTTP, authority may be `host` or `host:port` — allow-list entries must account for both forms.

### DNS

The AI harness container does not resolve internet destinations for proxied traffic — it only connects to loopback. Envoy receives the requested authority from the explicit proxy request and resolves allowed destinations from the sidecar container. Policy is applied before DNS resolution and before upstream connection.

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
* If the in-container socat bridge cannot start, the entrypoint fails.
* If a request does not match the allow-list, Envoy denies it.
* If a process bypasses proxy configuration, it has no network path due to `--network none`.

### Broad web research / Web Fetch

Direct URL fetching and broad internet research conflict with a narrow runtime allow-list. The baseline design does not open general internet egress for this use case. Future design work will define a separate retrieval plane.

---

## Authentication

Authentication spans the launcher (credential retrieval and injection) and the entrypoint (credential use and cleanup). The entrypoint's side — GitHub authentication initialization and removal of the token from the process environment — is described in the adda-dev-runtime technical design. This section covers the host-side credential lifecycle.

### Secrets

Two authentication secrets are required:
* **AI harness credential** — either a Claude Code OAuth token (Anthropic backend) or a DeepSeek API key (DeepSeek backend).
* **GitHub Token** — for repository access.

Both are stored in the host Secret Service keyring, retrieved by the launcher, and injected into the container at startup.

### Secret naming in keyring

| Secret | Service | Account | Key |
|---|---|---|---|
| Claude Code OAuth token | `adda-dev` | `claude` | `oauth` (default) |
| GitHub Token | `adda-dev` | `github` | repo-specific (e.g. `acme-token`) |
| DeepSeek API key | `adda-dev` | `deepseek` | `apikey` (default) |

All entries use the `adda-dev` service namespace. `account` identifies the target system; `key` identifies the credential within that system, configured per-repo in `adda-dev.env` via `ADDA_DEV_KEYRING_GITHUB_KEY`, `ADDA_DEV_KEYRING_CLAUDE_KEY`, and `ADDA_DEV_KEYRING_DEEPSEEK_KEY`. Multiple GitHub repos can coexist in one keyring by using distinct key values (e.g. `acme-token`, `otherrepo-token`).

### Retrieval

The launcher retrieves the required credentials at runtime:

```bash
CLAUDE_CODE_OAUTH_TOKEN=$(secret-tool lookup service adda-dev account claude key oauth)
GITHUB_TOKEN_=$(secret-tool lookup service adda-dev account github key {repo}-token)
```

If either lookup returns empty, the launcher fails fast with a bootstrap-procedure pointer.

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

## Filesystem and process hardening

### Container process privileges

The AI harness container is launched with:

```bash
--cap-drop ALL
--security-opt no-new-privileges
```

Expected runtime diagnostics:

```text
CapEff:        0000000000000000
NoNewPrivs:    1
```

No capability is added back for firewall or network configuration. Network enforcement is outside the container.

### Read-only root filesystem

The AI harness container root filesystem is read-only:

```bash
docker run --read-only
```

Writable paths are explicit tmpfs mounts. The design assumes a single effective runtime user inside the container. Writable mounts are owned by that runtime UID/GID and are private by default.

### Runtime user configuration

Defined in the launcher/project configuration:

```bash
ADDA_DEV_USER=adda
ADDA_DEV_UID=1000
ADDA_DEV_GID=1000
ADDA_DEV_HOME=/home/adda
```

The image must run as that user, or the entrypoint should warn that runtime UID/GID do not match the expected configuration.

### Writable tmpfs mounts

| Path | Mode | Exec? | Purpose |
|---|---|---|---|
| `/home/${ADDA_DEV_USER}` | `0700` | yes | AI harness state, gh config, git config, runtime state, shell config. |
| `/workspace` | `0700` | yes | Repository checkout, project writes, test/build output. |
| `/tmp` | `0700` | yes | Temporary files; exec permitted for tools that create and run temp scripts. |
| `/run` | `0700` | no | Runtime files and mounted proxy socket. |

`$HOME` and `/workspace` must permit execution because language tooling may install executable interpreters, virtualenvs, or scripts there. `/run` should be `noexec`; it exists for runtime/socket files.

Tmpfs sizes are configured by launcher variables:

```bash
ADDA_DEV_HOME_TMPFS_SIZE=500m
ADDA_DEV_WORKSPACE_TMPFS_SIZE=200m
```

Sizes are limits, not pre-allocated RAM reservations.

### Proxy socket mount

The Envoy Unix socket is bind-mounted into the container as an immediate child of `/run` (e.g. `/run/proxy.sock`). This avoids relying on nested parent directories under a tmpfs-mounted `/run`.

Socket permissions must allow the container runtime user to connect despite possible UID/GID mismatch between host user, Envoy sidecar process, and container user.

### Expected Docker-managed mounts

Docker provides managed files (`/etc/hosts`, `/etc/hostname`, `/etc/resolv.conf`). These do not by themselves provide network access and should be treated as expected Docker runtime configuration unless they contain unexpected content.
