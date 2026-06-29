# adda-dev-launcher — Architecture

## 1. Overview

The Python launcher is the host-side CLI that runs one AI-harness session per invocation: it reads host and project configuration, retrieves credentials from the host keyring, and starts the container together with its Envoy network sidecar. The invocation model is `adda-dev run <project> [--issue N]` — one project, one session.

It is replacing the Bash launcher (`launcher/adda-dev.sh`) and is being built incrementally under the redesign (#45 / #52). This document captures the **foundational** structure and decisions as they land — not an inventory of the code, which is the source of truth for specifics.

Adjacent documents, by viewpoint:
- **`conventions.md`** — how code is written (style, naming, types, imports, testing mechanics, output). This document does not restate those.
- **`conceptual-design.md`** / **`technical-design.md`** — the system's trust, threat, session, and network model (and the still-live Bash launcher).
- **`launcher-container-contract.md`** — the runtime interface between launcher and container.

---

## 2. Design principles

New work is measured against these.

**Domain-driven module boundaries.** Modules are split by concept, not by Python kind. There are no `enums` / `errors` / `constants` catch-all modules: an enum, exception, or constant lives in the module that owns the concept it belongs to. Only genuinely cross-cutting foundations — the root exception and the strict-model base — live in `common`. (Mechanics of when a module becomes a sub-package: `conventions.md`.)

**Open for extension, closed for modification.** New behaviour is added through defined extension points rather than by editing existing code. The LLM backend model is the worked example: a new vendor is a new backend-config subclass plus an enum value and a registry entry — existing backends and the load path are untouched.

**Explicit dependencies, no global state.** Components receive what they need as arguments rather than reaching for ambient state: load entry points take an injectable config directory, and a project is resolved against the project-defaults it is handed, not a global config object. There are no module-level singletons or shared mutable configuration. The run command will be the composition root that loads the entities and wires a session together.

**Configuration is data; a project is a domain entity.** `AppConfig` is a passive, validated value object describing the host. A `Project` is an active domain model whose TOML file is its *serialized state*; it uses configuration to resolve itself and to act, but it is not configuration. The two are never fused into a third "effective config" object — resolving a project against host defaults is the project's own behavior.

**Layered configuration, resolved downward.** Settings flow host → project → runtime; each layer overrides the one above, and per-invocation runtime overrides win. The launcher owns the host and project layers; the runtime layer arrives with the run command.

**Validate at the edge, fail fast.** External input (TOML files) is parsed and schema-validated the moment it is read, and unknown keys are rejected. Past that boundary the code works only with typed, already-valid models. Failures surface as typed exceptions rooted at a single `AddaDevError`; library layers raise, and only the CLI boundary renders them for the user. (The concrete output/exit mechanism is a convention, see `conventions.md`.)

**Thin host.** The host holds no project checkout; the only persistent host state is the config store under `~/.config/adda-dev/`. (Rationale: `conceptual-design.md`.)

**Self-contained environment.** uv provisions the interpreter and the lockfile-pinned dependencies — uv is the only host prerequisite for development. A new runtime or system dependency requires explicit justification.

---

## 3. Technology choices

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

## 4. Package layout

Source lives under `src/adda_dev/`. The structure follows **Onion Architecture**: three concentric rings with a strict inward-only import rule.

### Rings

**Shared kernel — `common.py`**
Cross-cutting foundations with no ring-specific concepts: `AddaDevError` root exception and `StrictModel` Pydantic base. May be imported by any ring.

**Domain ring — `domain/`**
Pure domain entities, value objects, and domain ports. No infrastructure dependencies.

Import rule: `domain/` imports only `common` and other `domain/` modules. It never imports `app/` or `infra/`.

**Application Services ring — `app/`**
Use cases that orchestrate domain entities. May import `domain/`.

Import rule: `app/` imports `domain/` and `common`. It never imports `infra/`.

**Infrastructure ring — `infra/`**
Filesystem I/O, external adapters (keyring), TOML parsing, CLI delivery mechanism, and the composition root. May import `domain/`, `app/`, and `common`.

Import rule: `infra/` is the outermost ring — it may import any other ring. Nothing imports `infra/` from an inner ring.

### Composition root

`infra/cli.py` is the composition root. It creates the `KeyringSecretSource` adapter, loads configuration, resolves domain entities, and wires them into the use case. The composition root is the only place where all rings meet.

### Port pattern

The credential port (`SecretSource` ABC, in `domain/credentials.py`) lets domain entities retrieve secrets without depending on the keyring library. The Infrastructure ring provides `KeyringSecretSource` as the production adapter; tests provide `FakeSecretSource`. The same pattern applies to future ports for container execution and session display (#59, #60).

### Module table

| Module | Ring | Concern |
|---|---|---|
| `common` | Shared kernel | `AddaDevError` root exception and `StrictModel` Pydantic base |
| `domain/tmpfs` | Domain | tmpfs sizing value objects and their override merge |
| `domain/credentials` | Domain | `SecretSource` port, `Secret` ABC, `SecretError` |
| `domain/github` | Domain | `GitHub` domain model (credential retrieval via `SecretSource`) |
| `domain/llm` | Domain | `LlmBackend` enum, `AnthropicBackend`, `DeepSeekBackend` frozen dataclasses |
| `domain/project` | Domain | `Project` domain entity and `ProjectNotFoundError` |
| `app/run` | Application | `run_session()` use case: retrieve credentials and display session info |
| `infra/store` | Infrastructure | Config-directory resolution, safe file-name validation, TOML load+validate |
| `infra/keyring_source` | Infrastructure | `KeyringSecretSource` — OS keyring adapter for the `SecretSource` port |
| `infra/llm` | Infrastructure | LLM config DTOs (`AnthropicConfigModel`, `DeepSeekConfigModel`, `LlmConfig`) and `resolve_backend()` |
| `infra/config` | Infrastructure | Host config DTOs (`AppConfig`, `ProjectDefaults`, `ContainerEngine`) and `load_app_config()` |
| `infra/project` | Infrastructure | Project file DTOs (`ProjectFileModel`, `GitHubFileModel`) and `load_project()` |
| `infra/cli` | Infrastructure | Typer entry point and composition root |

The later layers of the launcher — container/network execution and tmux session management — extend this graph as they are built.

---

## 5. Configuration and project model

**Two entities.** `AppConfig` is the host-wide configuration; a `Project` is a domain model. The project's TOML file is parsed into a serialized file shape and then *resolved* into the fully-typed `Project` the rest of the launcher uses. Fields belong to the code, not to this document.

**The config store and its boundary.** All host state lives under `~/.config/adda-dev/` (XDG; `$XDG_CONFIG_HOME` relocates it — there is no config-directory flag). The `store` module is the persistence boundary: it exposes only the entry point into that folder, safe file-name validation, and TOML loading — it knows no filenames. Each entity owns its own location *within* the store: `AppConfig` is the root `config.toml`; a `Project` is an entry in the `projects/` registry. Persistence mechanics stay in one place; layout knowledge stays with the entities that own it.

**Resolution.** A project is resolved by applying its optional overrides onto the host's project-defaults, with the merge logic living on the value object it concerns. Host configuration is optional — absent means built-in defaults; a project is mandatory — absent is an error. A project actively selects its LLM backend: it inherits no default backend and cannot override vendor settings, which are host-wide.

**Errors.** Persistence-level failures are vendor-neutral (parse, schema validation, invalid file name); a domain-level failure (project not found) lives with the domain. All derive from `AddaDevError`, so a single catch at the CLI boundary is sufficient.
