# adda-dev-launcher — Architecture

## 1. Overview

The Python launcher is the host-side CLI that runs one AI-harness session per invocation: it reads host and project configuration, retrieves credentials from the host keyring, and starts the container together with its Envoy network sidecar. The invocation model is `adda-dev run <project> [--issue N]` — one project, one session.

It is replacing the Bash launcher (`launcher/adda-dev.sh`) and is being built incrementally under the redesign (#45 / #52). This document captures the **foundational** structure and decisions as they land — not an inventory of the code, which is the source of truth for specifics.

Adjacent documents, by viewpoint:
- **`conventions.md`** — how code is written (style, naming, types, imports, testing mechanics, output). This document does not restate those.
- **`conceptual-design.md`** / **`technical-design.md`** — the system's trust, threat, session, and network model (and the still-live Bash launcher).
- **`launcher-container-contract.md`** — the runtime interface between launcher and container.

---

## 2. Architectural foundations

### Onion Architecture over a domain-driven model

The launcher is structured using **Onion Architecture** applied to a **domain-driven** model. These are not independent choices — Onion Architecture is the structural mechanism that enforces what domain-driven design requires.

**Domain-driven design** anchors the system's structure in its core problem: launching a configured dev session for a named project. The domain model captures what the system knows about that problem — what a project is, which providers exist, how credentials are scoped — independent of how that knowledge is acquired, stored, or delivered. A `Project` entity is the same object whether assembled from a TOML file, constructed by a test, or produced by a future API; its correctness does not depend on its origin.

**Onion Architecture** enforces this structurally: the codebase is organised as concentric rings with one rule — dependencies always point inward. The domain model sits at the centre; infrastructure (TOML I/O, keyring, CLI delivery) sits at the outside. Infrastructure adapts to the domain; the domain never adapts to infrastructure. This is a structural guarantee, not a convention: a ring violation is a visible cross-ring import.

### Domain model

The domain for this system is the *session launch*: a named project running in a container image, authenticated against an LLM provider and a GitHub identity, with a configured tmpfs layout.

**Entities** have identity that persists across invocations — they are the aggregate roots, each managed through a repository port:
- `Project` — identified by name; owns the selection of image, provider, and GitHub identity
- `Session` — identified by `session_id`; owns runtime directory lifecycle

**Value objects** are immutable, equal by value, with no independent identity:
- `TmpfsSizes`, `TmpfsOverride` — the tmpfs layout and its per-project override
- `GitHub` — GitHub identity and credential-retrieval parameters; owned by `Project`, embedded directly
- `AnthropicProvider`, `DeepSeekProvider` — LLM credential-retrieval parameters; loaded from host config via `ProviderRepository`, not aggregate roots

**Domain ports** — beyond repository ports, the domain defines several secondary ports: `SecretSource` for credential retrieval by entities (the OS keyring, a test double, or any other source — entities never know which), and `ProxySidecar`, `AddaPrimaryContainer`, `Window`, and `SessionManager` for the session execution and lifecycle layer. The domain owns each contract; infrastructure satisfies it. (Port-to-adapter mapping: §5 Port pattern.)

**Repository ports** — whenever the domain needs to retrieve or manage an aggregate, a repository port is defined in `domain/` and implemented in `infra/`. The domain owns the contract; infrastructure satisfies it. This keeps storage mechanics out of the domain and application rings entirely. Current repository ports: `ProjectRepository`, `ProviderRepository`, `SessionRepository`.

Two rules govern the design. First, aggregates reference other aggregates by **identity value**, never by direct object embedding — a value-typed reference (an enum, a name string) acts as the foreign key. The aggregate on the other end is not nested; it is retrieved separately when needed. Second, repositories are **independent** — they do not call each other. The application service is the only place that composes aggregates from multiple repositories; it calls each repository in turn and assembles the result.

### Rings

**Shared kernel** (`common.py`) — cross-cutting foundations importable by any ring: the root exception type and the strict-model Pydantic base.

**Domain** (`domain/`) — the entities, value objects, and the `SecretSource` port described above. Contains no infrastructure dependencies. The stable centre the rest of the system is built around.

**Application Services** (`app/`) — use-case orchestration: the sequence of domain operations that constitutes a launcher session. Imports domain; never imports infrastructure. This ring holds the *algorithm* of the launcher, decoupled from how it is invoked and how domain objects are assembled.

**Infrastructure** (`infra/`) — everything that touches the outside world: TOML I/O, the OS keyring adapter, the CLI entry point, and the composition root that assembles the system from its parts. Imports any inner ring; nothing inner imports it. Technical mechanism (container engine, subprocess execution) also lives here, with its own internal port/adapter split to enable future swaps (e.g., Docker↔Podman) — these infra-internal ports are never named by an inner ring.

### Session lifecycle

The session launch sequence — create a session record, start the proxy sidecar, finalize the contract spec, open the primary window, run the primary container, open secondary windows, wait for the primary to exit, tear everything down in order — is mode-independent. Execution mode (Direct terminal today; tmux in the next phase) determines only *how* windows are created and what mode-specific teardown involves, not the sequence itself. `SessionManager` encodes this invariant algorithm as a domain base class; subclasses supply `create_window()` and two optional hooks (`_open_secondary_windows`, `_teardown`).

**The two lifecycle owners.** `SessionManager` coordinates two objects that each own a running process for the duration of the session:

- **`AddaPrimaryContainer`** — foreground. `start(session, spec, window)` takes a `Window`; the primary container's interactive TTY is bound to that window for the session's duration.
- **`ProxySidecar`** — background. `start(session)` manages the Envoy container internally (detached) and returns the host-side proxy socket path. `SessionManager._launch()` passes this return value to `draft.finalize(host_socket)` to produce the final `ContractSpec` — the reason the sidecar must start before the spec can be finalized.

Both lifecycle owners are also extensibility surfaces for secondary windows in the tmux layout (planned in the next phase): `AddaPrimaryContainer` will expose a Window-accepting method for an interactive shell into the running container; `ProxySidecar` will expose one for a log watcher. Both are foreground. The `_open_secondary_windows()` hook on `SessionManager` is where subclasses call these methods.

**`attach` is session control, not container lifecycle.** The lifecycle owners own `start`/`stop`. Attaching — blocking until the session ends — is mode-specific: Direct mode waits on the primary process; tmux mode attaches to the tmux session. It belongs on the `SessionManager`/`Window` side.

**Teardown guarantee.** `SessionManager.run()` wraps `_launch()` in `try/finally`, so `_terminate()` fires regardless of where launch fails — whether the container pull fails mid-launch, a secondary window raises, or any other mid-sequence error. SIGTERM is converted to `SystemExit(128 + signum)` in `infra/cli.py` — a `BaseException` that propagates through `finally` and cannot be swallowed by `except Exception`. Together these make teardown reliable under all failure modes.

**Teardown ordering.** `_terminate()` runs: close windows → `container.stop()` → `_teardown()` hook → `sidecar.stop()` → `repo.delete()`. The primary container stops before the sidecar because it depends on the sidecar's proxy socket. The session record is deleted last so it remains available if any teardown step fails.

### Launcher-container contract model

`ContractSpec` is the domain model of the launcher's §1 obligations from `launcher-container-contract.md` — not a command builder, but a typed representation of exactly what the launcher must provide. A value belongs in `ContractSpec` only if it maps to a §1 contract obligation. Values that are contract-mandated defaults (e.g., the hardening booleans `cap_drop_all=True`) are domain field defaults; implementation constants not specified by the contract (e.g., tmpfs option format strings) belong in the infra adapter as private values.

**`ContractSpecDraft` models a temporal dependency.** The proxy socket path is runtime-determined — the sidecar must be running before it is known. `ContractSpecDraft.initialize(project, provider, issue_id)` builds the pre-sidecar shape; `finalize(host_socket)` locks in the socket path and returns the immutable `ContractSpec`. This is why `SessionManager._launch()` starts the sidecar first, captures the returned socket path, and immediately calls `draft.finalize()`.

**Secret isolation.** `ContractTranslator.translate()` produces `ContractProcessParams(args, env)`. Secret values must appear only in `env` — never in `args`. `args` carries flag names only (e.g., `--env KEY`); the secret value is injected into the subprocess environment via `env`. All `ContractTranslator` implementations must honor this constraint.

**Launcher configuration that is not a contract obligation belongs in the adapter, not the spec.** The container command override (`-- CMD` on the CLI) is not a §1 contract obligation and does not belong in `ContractSpec` or `SessionManager`. It is held on `AddaPrimaryContainerImpl` at construction time and passed to the engine at run time.

---

## 3. Design principles

New work is measured against these.

**Domain-driven module boundaries.** Modules are split by concept, not by Python kind. There are no `enums` / `errors` / `constants` catch-all modules: an enum, exception, or constant lives in the module that owns the concept it belongs to. Only genuinely cross-cutting foundations — the root exception and the strict-model base — live in `common`. (Mechanics of when a module becomes a sub-package: `conventions.md`.)

**Open for extension, closed for modification.** New behaviour is added through defined extension points rather than by editing existing code. The LLM provider model is the worked example: a new vendor is a new provider-config subclass plus an enum value and a registry entry — existing providers and the load path are untouched.

**Explicit dependencies, no global state.** Components receive what they need as arguments rather than reaching for ambient state: a project is resolved against the project-defaults it is handed, not a global config object. Storage roots are resolved from XDG env vars at call time rather than injected as path parameters. There are no module-level singletons or shared mutable configuration. The composition root (`infra/cli.py`) is the single place that assembles and wires everything together.

**Configuration is data; a project is a domain entity.** `AppConfig` is a passive host-configuration value object. `Project` is a domain entity whose TOML file is its serialized state; it is not configuration. The two are never fused into a combined "effective config" — resolving a project against host defaults is the project's own behaviour.

**Layered configuration, resolved downward.** Settings flow host → project → runtime; each layer overrides the one above, and per-invocation runtime overrides win. The launcher owns the host and project layers; the runtime layer arrives with the run command.

**Validate at the edge, fail fast.** External input (TOML files) is parsed and schema-validated the moment it is read, and unknown keys are rejected. Past that boundary the code works only with typed, already-valid models. Failures surface as typed exceptions rooted at a single `AddaDevError`; library layers raise, and only the CLI boundary renders them for the user. (The concrete output/exit mechanism is a convention, see `conventions.md`.)

**Thin host.** The host holds no project checkout; the only persistent host state is the config store under `~/.config/adda-dev/`. (Rationale: `conceptual-design.md`.)

**Self-contained environment.** uv provisions the interpreter and the lockfile-pinned dependencies — uv is the only host prerequisite for development. A new runtime or system dependency requires explicit justification.

---

## 4. Technology choices

| Role | Choice | Rationale |
|---|---|---|
| Language | Python | Ecosystem covers distribution, CLI, config, keyring, and testing — no custom infrastructure |
| Distribution | `uv tool install <wheel-url>` from GitHub Releases | uv manages the Python runtime, so uv is the only host prerequisite |
| Packaging / versioning | `pyproject.toml` + uv; `hatch-vcs` | Version stamped from git tags |
| CLI framework | Typer | Typed-function API over Click; integrates with Rich |
| Terminal output | Rich | User-facing output; pairs with Textual |
| Interactive prompts | Textual | Rich-based TUI; not required for the MVP |
| Config format / validation | `tomlkit` + Pydantic v2 | tomlkit reads now and writes later (project registry editing); Pydantic gives typed, strict validation |
| Keyring | `keyring` + `jeepney` | Pure-Python DBus; no native build, wheel stays `py3-none-any` |
| Subprocess / process | stdlib | `os.execvp` for process replacement; `subprocess` for the container run |
| Terminal multiplexer | `tmux -L <name>` | Dedicated server, isolated from the user's tmux |
| Container engine | Docker or Podman | Selected via `AppConfig` (`container_engine`); no auto-detection |

---

## 5. Package layout

Source lives under `src/adda_dev/`. The ring structure defined in §2 maps directly to packages: `domain/`, `app/`, `infra/`, and `common.py` as the shared kernel.

**Import rule:** dependencies always point inward. `domain/` imports only `common` and sibling `domain/` modules. `app/` adds `domain/`. `infra/` may import any ring. No inner ring imports `infra/`.

### Composition root

`infra/cli.py` is the composition root. It creates the `KeyringSecretSource` adapter, loads configuration, resolves domain entities, and wires them into the use case. The composition root is the only place where all rings meet.

### Port pattern

Two distinct kinds of ports appear in this codebase:

**Domain-defined ports** — the SPI the domain owns. The domain defines the contract; infrastructure satisfies it. No inner ring knows the adapter:

- **Credential retrieval:** `SecretSource` (`domain/credentials.py`) → `KeyringSecretSource` (`infra/keyring_source.py`)
- **Aggregate retrieval:** `ProjectRepository` (`domain/project.py`) → `TomlProjectRepository` (`infra/project.py`); `ProviderRepository` (`domain/llm.py`) → `LlmConfigProviderRepository` (`infra/llm.py`); `SessionRepository` (`domain/session.py`) → `FsSessionRepository` (`infra/session.py`)
- **Output delivery:** `Output` Protocol (`common.py`) → `RichOutput` (`infra/output.py`)
- **Proxy sidecar:** `ProxySidecar` (`domain/proxy.py`) → `EnvoySidecar` (`infra/proxy.py`)
- **Primary container lifecycle:** `AddaPrimaryContainer` (`domain/adda_container.py`) → `AddaPrimaryContainerImpl` (`infra/adda_container.py`)
- **Session window:** `Window` (`domain/window.py`) → `DirectWindow` (`infra/session.py`)
- **Session lifecycle:** `SessionManager` (`domain/session_manager.py`) → `DirectSessionManager` (`infra/session.py`)

**Infra-internal ports** — technical mechanism abstracted within `infra/` to enable adapter swaps (e.g., Docker↔Podman) without touching inner rings. Inner rings never name these ports.

- **Container engine:** `ContainerEngine` (`infra/container.py`) → `DockerEngine` (`infra/container.py`); `create_engine()` factory builds the engine and emits the startup banner + rootless warning
- **Subprocess execution:** `ProcessRunner`/`ProcessHandle` (`infra/process.py`) → `DefaultRunner`, `CapturedOutputRunner` (`infra/process.py`)

### Package structure

| Location | Role |
|---|---|
| `common.py` | Shared kernel — `AddaDevError` root exception and `StrictModel` Pydantic base; importable by any ring |
| `domain/` | Domain ring — entities, value objects, and all domain ports |
| `app/` | Application ring — use-case orchestration; imports domain only |
| `infra/` | Infrastructure ring — all adapters, the CLI entry point, and the composition root |
| `infra/cli.py` | CLI entry point and composition root; the only place all rings meet |

---

## 6. Configuration and project model

**Two entities.** `AppConfig` is the host-wide configuration; a `Project` is a domain model. The project's TOML file is parsed into a serialized file shape and then *resolved* into the fully-typed `Project` the rest of the launcher uses. Fields belong to the code, not to this document.

**The config store and its boundary.** All host state lives under `~/.config/adda-dev/` (XDG; `$XDG_CONFIG_HOME` relocates it — there is no config-directory flag). The `store` module is the persistence boundary: it exposes only the entry point into that folder, safe file-name validation, and TOML loading — it knows no filenames. Each entity owns its own location *within* the store: `AppConfig` is the root `config.toml`; a `Project` is an entry in the `projects/` registry. Persistence mechanics stay in one place; layout knowledge stays with the entities that own it.

**Resolution.** A project is resolved by applying its optional overrides onto the host's project-defaults, with the merge logic living on the value object it concerns. Host configuration is optional — absent means built-in defaults; a project is mandatory — absent is an error. A project actively selects its LLM provider: it inherits no default provider and cannot override vendor settings, which are host-wide.

**Errors.** Persistence-level failures are vendor-neutral (parse, schema validation, invalid file name); a domain-level failure (project not found) lives with the domain. All derive from `AddaDevError`, so a single catch at the CLI boundary is sufficient.
