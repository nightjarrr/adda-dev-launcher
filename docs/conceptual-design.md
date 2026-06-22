# adda-dev-launcher — Conceptual Design

**`adda-dev-launcher`** is the host-side launcher for the **ADDA Dev Runtime** (ADDA: Agentic Development with Durable Artifacts) — the overall development environment system comprising the launcher, the network proxy sidecar, and the AI harness container working together as a coordinated session. The launcher creates and destroys sessions, retrieves credentials from the host keyring, and enforces the isolation boundaries described in this document. [`adda-dev-runtime`](https://github.com/nightjarrr/adda-dev-runtime) is the companion repository that owns the container-side implementation.

This document establishes its conceptual design: the trust model, threat model, session model, and security principles the launcher enforces. It is a design rationale document — the place to understand *why* the launcher is designed the way it is and what trade-offs it makes.

The launcher implements the [ADDA SDLC](https://github.com/nightjarrr/molim/blob/main/docs/adda-sdlc.md) — the vendor-agnostic development methodology in which a **feature workflow** is one unit of work: a single GitHub Issue carried out in one AI harness session. The **AI harness** is the program that implements the agentic loop; the **AI agent** is the AI actor that executes inside it and drives the feature workflow. **Subagents** are subordinate agents spawned by the AI agent; they share the parent's container and do not get separate containers or network proxies.

**Audience: human Project Owner only.** Read at setup time and when modifying the environment. Not part of any agent's runtime context.

For the concrete implementation of this design — startup sequence, configuration variables, network allow-list, authentication specifics — see [`docs/technical-design.md`](technical-design.md).

For the contract between the launcher and the container it starts, see [`docs/launcher-container-contract.md`](launcher-container-contract.md).

For the container-internal architecture — Tier 1/2/3 stack and tier responsibilities — see [`docs/adda-dev-runtime-design.md`](https://github.com/nightjarrr/adda-dev-runtime/blob/main/docs/adda-dev-runtime-design.md) in adda-dev-runtime.

Throughout, `{owner}` and `{repo}` refer to the GitHub namespace and repository name of the project.

---

## Design principles

### Ephemeral runtime

The launcher creates a runtime for one feature workflow and destroys it on exit. No state persists across container exits; resuming work means the launcher creates a new runtime and the agent rebuilds context from GitHub. This is an intentional and accepted trade-off for isolation and reproducibility.

*Broader design intent:* the ephemeral runtime pairs with a stateless agent and stateful GitHub. The AI agent carries no state across session exits, and GitHub is the persistence layer for all project work — commits, Issues (including hierarchies, cross-links, and comments), Pull Requests and their review trails, and GitHub API state (labels, milestones, phase tracking). The launcher enforces the ephemeral boundary; the stateless-agent and persistent-GitHub patterns are implemented by adda-dev-runtime inside the container, not launcher responsibilities.

### Defense in depth

The launcher establishes three concentric boundaries that protect the host and project from code running inside the development environment:

1. **Container isolation** — the launcher starts the AI harness container with no host filesystem, process, device, display, container engine socket, or network namespace access beyond what it explicitly grants.
2. **Proxy-based network perimeter** — the launcher starts a per-session network proxy sidecar that enforces a default-deny domain allow-list on all outbound traffic. The proxy runs outside the container trust boundary — running enforcement inside the container would make it defeatable by the untrusted code it protects. Each session gets its own dedicated proxy instance; sessions do not share a proxy.
3. **AI harness permission configuration** — the third boundary, enforced inside the container: the AI harness applies a least-privilege permission model governing what agents, skills, and tools can do. This boundary is part of the overall defense-in-depth design but is not enforced by the launcher.

Two further protections bound the impact of credential exposure:

- **Host-side keyring** — the launcher retrieves authentication tokens from the host keyring (the OS-native secret store) on demand; tokens never reside in plaintext on host disk.
- **Token scoping** — the GitHub Token the launcher supplies is scoped to a single repository with no administration permissions, bounding GitHub blast radius.

### Host launcher and network proxy are trusted perimeter components

The AI harness container is treated as untrusted. Nothing inside it is assumed to be non-exploitable. The launcher and the per-session network proxy sidecar it starts are therefore part of the trusted computing base for network and runtime isolation. A user who deliberately bypasses the launcher or weakens the network proxy policy is outside the protection model.

### No plaintext secrets on host disk

Authentication tokens live in the host keyring. The launcher retrieves tokens on demand. There is no project `.env` containing secrets, no credentials file, and no token in shell history.

---

## Components

The ADDA Dev Runtime is composed of four distinct components. Understanding what each component is and its trust level is essential for the design principles and threat model to be meaningful.

### Host system

The machine on which the development environment runs. The only fully trusted environment. It carries the host keyring (secrets at rest) and the launcher program. The container engine runs here. The host system is never directly accessible from inside the AI harness container. No development tooling — git, the GitHub CLI, language runtimes, or project-specific tools — is required on the host; all of that runs inside containers.

### Launcher

A host-side program that creates and tears down a single development session. The launcher retrieves credentials from the host keyring, starts the network proxy sidecar, assembles and runs the AI harness container with its required security constraints, and cleans up on exit. The workflow is terminal-first; the launcher creates a plain isolated container — not a Dev Container (Microsoft's Dev Containers specification, which adds host-container IPC sockets and direct IDE tooling integration to a container) — with none of those host connections. It is the only component that can set session parameters. The launcher is a trusted perimeter component.

### Network proxy sidecar

A per-session network perimeter proxy started by the launcher. It runs as a separate component outside the AI harness container trust boundary and enforces a default-deny domain allow-list on all outbound traffic from the session. The network proxy sidecar is a trusted perimeter component. Each session gets its own dedicated proxy instance; sessions do not share a proxy.

### AI harness container

The isolated, ephemeral runtime in which the AI agent and all development tooling run. Explicitly treated as untrusted — the launcher gives it no general network access (outbound traffic is routed through the network proxy sidecar) and mounts a read-only root filesystem with writable paths as explicit tmpfs mounts. For the container's internal design, see the adda-dev-runtime conceptual design.

---

## Trust model

| Component | Trust level | Rationale |
|---|---|---|
| Host system | Fully trusted | The user's machine; outside the threat boundary |
| Launcher | Trusted | User-controlled; part of the trusted computing base |
| Network proxy sidecar | Trusted | Started by the launcher outside the container; enforces network policy |
| AI harness container | **Untrusted** | May run exploited or manipulated code |

The boundary between trusted and untrusted runs at the container wall. The launcher establishes this boundary; network enforcement sits outside it — in the network proxy sidecar — specifically because components inside the boundary cannot be trusted to enforce their own rules.

---

## Threat model

### Primary threat: host compromise from code inside the development environment

The launcher must prevent any code, tool, dependency, or AI agent running inside the AI harness container from affecting the host system.

The launcher constrains the container with a set of non-negotiable properties: no host namespace access, no container engine socket, non-root user, minimal OS-level privileges, read-only root filesystem, and no general network egress.

### Limits of container isolation

Container isolation reduces likelihood and blast radius; it does not reduce risk to zero. The host kernel must be patched. Image provenance, base-image discipline, pinned digests, CI provenance, and minimal runtime privileges are part of the mitigation. A determined attacker exploiting an unpatched container escape CVE is outside of this design's guarantee.

### Prompt injection

Adversarial content in the agent's context may manipulate its actions within the session.

Launcher-enforced mitigations: ephemeral runtime boundary limits persistence and blast radius; narrow GitHub Token scope prevents cross-repository or account-level damage; network egress allow-list limits where compromised code can communicate. The container contributes complementary mitigations — described in the adda-dev-runtime conceptual design.

Residual risk: hostile content may influence changes on the current branch until caught at review.

### Malicious dependencies

A dependency of the launcher or proxy sidecar may execute hostile code on the host. Because these components run in the trusted perimeter, a compromise here is higher-severity than an in-container compromise. The launcher script, network proxy sidecar binary, and any host OS libraries they depend on are the relevant attack surface. Mitigations: keep the launcher minimal; pin and audit upstream dependencies of both the launcher and the proxy sidecar; keep the host OS patched.

Container-side dependency classes are described in the adda-dev-runtime conceptual design.

Residual risk: a compromised host-side component operates outside all container isolation guarantees.

### Network exfiltration

A compromised tool or manipulated AI agent may attempt to send repository contents, tokens, or other data to an attacker-controlled endpoint.

Primary mitigation: the launcher gives the container no network interface beyond loopback and routes all outbound traffic through the network proxy sidecar via `HTTP_PROXY`/`HTTPS_PROXY`; processes that use proxy-aware HTTP clients reach only allow-listed domains, and processes that ignore proxy configuration have no network path to use.

### Token theft

The container must hold credentials to function. Mitigations: the launcher supplies a GitHub Token scoped to a single repository with no administration permissions; the AI vendor token (the credential the AI harness uses to call the AI provider's API) is revocable; exfiltration routes are constrained by the network allow-list; the launcher never stores tokens in plaintext on host disk.

Accepted residual risk: an attacker in a live session can use available credentials within their granted scope until the session is terminated or tokens are revoked.

### Quota and resource abuse

A runaway AI agent session or hostile instruction may consume API quota, GitHub API rate limits, or host CPU and memory. Mitigations: the launcher's ephemeral container teardown stops further consumption; GitHub API rate limits apply naturally.

---

## Session model

One development session is a coordinated unit — the launcher creates one of each component together and destroys them together:

| Concept | Mapping |
|---|---|
| One GitHub Issue | One feature workflow |
| One feature workflow | One AI harness session |
| One AI harness session | One AI harness container |
| One AI harness container | One network proxy sidecar |
| One AI harness container | One host terminal session |

Subagents run inside the parent AI harness process and share its container. They do not get separate containers.

Multiple features may run concurrently. Each session is fully isolated from others, sharing no state except through GitHub.

The launcher creates a session when work begins and destroys it when the session exits — the host terminal running the launcher is the session boundary. Resuming work means the launcher creates a new runtime; state is reloaded from GitHub.

---

## Deferred questions

The following are recognized but not addressed by the current design:

1. **Broad web retrieval plane** — define how user-approved direct URL fetch and research should work without opening general egress from the container.
2. **Live allow-list management** — explore whether network proxy policy should be reloadable without sidecar restart, and whether a UI/control plane is justified.
3. **Credential hiding behind proxy/gateway** — investigate whether future API-specific gateways can inject auth headers so selected tools do not receive raw tokens.
4. **Stronger sandboxing** — evaluate alternative container isolation technologies (e.g. gVisor, VM-based runtimes) if kernel escape risk becomes a higher priority.
5. **Container resource limits** — CPU and memory quotas for the AI harness container are not currently enforced. Evaluate container runtime resource constraint features.
