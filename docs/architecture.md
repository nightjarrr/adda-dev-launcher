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

**Domain-driven design** anchors the system's structure in its core problem: launching a configured dev session for a named project. The domain model captures what the system knows about that problem — what a project is, which backends exist, how credentials are scoped — independent of how that knowledge is acquired, stored, or delivered. A `Project` entity is the same object whether assembled from a TOML file, constructed by a test, or produced by a future API; its correctness does not depend on its origin.

**Onion Architecture** enforces this structurally: the codebase is organised as concentric rings with one rule — dependencies always point inward. The domain model sits at the centre; infrastructure (TOML I/O, keyring, CLI delivery) sits at the outside. Infrastructure adapts to the domain; the domain never adapts to infrastructure. This is a structural guarantee, not a convention: a ring violation is a visible cross-ring import.

### Domain model

The domain for this system is the *session launch*: a named project running in a container image, authenticated against an LLM backend and a GitHub identity, with a configured tmpfs layout.

**Entities** have identity that persists across invocations — they are the aggregate roots, each managed through a repository port:
- `Project` — identified by name; owns the selection of image, backend, and GitHub identity
- `Session` — identified by `session_id`; owns runtime directory lifecycle

**Value objects** are immutable, equal by value, with no independent identity:
- `TmpfsSizes`, `TmpfsOverride` — the tmpfs layout and its per-project override
- `GitHub` — GitHub identity and credential-retrieval parameters; owned by `Project`, embedded directly
- `AnthropicBackend`, `DeepSeekBackend` — LLM credential-retrieval parameters; loaded from host config via `BackendRepository`, not aggregate roots

**Domain port** — the domain defines one secondary port: `SecretSource`. Entities retrieve credentials through this interface without knowing whether the source is the OS keyring, a test double, or anything else. The domain owns the contract; infrastructure satisfies it.

**Repository ports** — whenever the domain needs to retrieve or manage an aggregate, a repository port is defined in `domain/` and implemented in `infra/`. The domain owns the contract; infrastructure satisfies it. This keeps storage mechanics out of the domain and application rings entirely. Current repository ports: `ProjectRepository`, `BackendRepository`, `SessionRepository`.

Two rules govern the design. First, aggregates reference other aggregates by **identity value**, never by direct object embedding — a value-typed reference (an enum, a name string) acts as the foreign key. The aggregate on the other end is not nested; it is retrieved separately when needed. Second, repositories are **independent** — they do not call each other. The application service is the only place that composes aggregates from multiple repositories; it calls each repository in turn and assembles the result.

### Rings

**Shared kernel** (`common.py`) — cross-cutting foundations importable by any ring: the root exception type and the strict-model Pydantic base.

**Domain** (`domain/`) — the entities, value objects, and the `SecretSource` port described above. Contains no infrastructure dependencies. The stable centre the rest of the system is built around.

**Application Services** (`app/`) — use-case orchestration: the sequence of domain operations that constitutes a launcher session. Imports domain; never imports infrastructure. This ring holds the *algorithm* of the launcher, decoupled from how it is invoked and how domain objects are assembled.

**Infrastructure** (`infra/`) — everything that touches the outside world: TOML I/O, the OS keyring adapter, the CLI entry point, and the composition root that assembles the system from its parts. Imports any inner ring; nothing inner imports it.

---

## 3. Design principles

New work is measured against these.

**Domain-driven module boundaries.** Modules are split by concept, not by Python kind. There are no `enums` / `errors` / `constants` catch-all modules: an enum, exception, or constant lives in the module that owns the concept it belongs to. Only genuinely cross-cutting foundations — the root exception and the strict-model base — live in `common`. (Mechanics of when a module becomes a sub-package: `conventions.md`.)

**Open for extension, closed for modification.** New behaviour is added through defined extension points rather than by editing existing code. The LLM backend model is the worked example: a new vendor is a new backend-config subclass plus an enum value and a registry entry — existing backends and the load path are untouched.

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

Ports are defined in the domain or shared kernel; infrastructure provides the production adapters. Three port families are active:

- **Credential retrieval:** `SecretSource` (`domain/credentials.py`) → `KeyringSecretSource` (`infra/keyring_source.py`)
- **Aggregate retrieval:** `ProjectRepository` (`domain/project.py`) → `TomlProjectRepository` (`infra/project.py`); `BackendRepository` (`domain/llm.py`) → `LlmConfigBackendRepository` (`infra/llm.py`); `SessionRepository` (`domain/session.py`) → `FsSessionRepository` (`infra/session.py`)
- **Output delivery:** `Output` Protocol (`common.py`) → `RichOutput` (`infra/output.py`)

The same pattern will apply to future ports for container execution and session display (#59, #60).

### Module table

| Module | Ring | Concern |
|---|---|---|
| `common` | Shared kernel | `AddaDevError` root exception and `StrictModel` Pydantic base |
| `domain/tmpfs` | Domain | tmpfs sizing value objects and their override merge |
| `domain/credentials` | Domain | `SecretSource` port, `Secret` ABC, `SecretError` |
| `domain/github` | Domain | `GitHub` domain model (credential retrieval via `SecretSource`) |
| `domain/llm` | Domain | `LlmBackend` enum, `AnthropicBackend`, `DeepSeekBackend` frozen dataclasses, `BackendRepository` port |
| `domain/project` | Domain | `Project` domain entity, `ProjectNotFoundError`, `ProjectRepository` port |
| `domain/session` | Domain | `Session` entity, `SessionNotFoundError`, `SessionRepository` port |
| `app/run` | Application | `run_session()` use case: composes project and backend aggregates, retrieves credentials, displays session info |
| `infra/store` | Infrastructure | XDG-aware storage root resolution (`StorageArea`, `resolve_storage_root`), safe file-name validation, TOML load+write |
| `infra/session` | Infrastructure | `SessionFileModel` DTO and `FsSessionRepository` — filesystem-backed session lifecycle |
| `infra/keyring_source` | Infrastructure | `KeyringSecretSource` — OS keyring adapter for the `SecretSource` port |
| `infra/llm` | Infrastructure | LLM config DTOs (`AnthropicConfigModel`, `DeepSeekConfigModel`, `LlmConfig`) and `LlmConfigBackendRepository` |
| `infra/config` | Infrastructure | Host config DTOs (`AppConfig`, `ProjectDefaults`, `ContainerEngine`) and `load_app_config()` |
| `infra/project` | Infrastructure | Project file DTOs (`ProjectFileModel`, `GitHubFileModel`) and `TomlProjectRepository` |
| `infra/output` | Infrastructure | `RichOutput` — Rich terminal adapter for the `Output` port |
| `infra/cli` | Infrastructure | Typer entry point and composition root |

The later layers of the launcher — container/network execution and tmux session management — extend this graph as they are built.

---

## 6. Configuration and project model

**Two entities.** `AppConfig` is the host-wide configuration; a `Project` is a domain model. The project's TOML file is parsed into a serialized file shape and then *resolved* into the fully-typed `Project` the rest of the launcher uses. Fields belong to the code, not to this document.

**The config store and its boundary.** All host state lives under `~/.config/adda-dev/` (XDG; `$XDG_CONFIG_HOME` relocates it — there is no config-directory flag). The `store` module is the persistence boundary: it exposes only the entry point into that folder, safe file-name validation, and TOML loading — it knows no filenames. Each entity owns its own location *within* the store: `AppConfig` is the root `config.toml`; a `Project` is an entry in the `projects/` registry. Persistence mechanics stay in one place; layout knowledge stays with the entities that own it.

**Resolution.** A project is resolved by applying its optional overrides onto the host's project-defaults, with the merge logic living on the value object it concerns. Host configuration is optional — absent means built-in defaults; a project is mandatory — absent is an error. A project actively selects its LLM backend: it inherits no default backend and cannot override vendor settings, which are host-wide.

**Errors.** Persistence-level failures are vendor-neutral (parse, schema validation, invalid file name); a domain-level failure (project not found) lives with the domain. All derive from `AddaDevError`, so a single catch at the CLI boundary is sufficient.
