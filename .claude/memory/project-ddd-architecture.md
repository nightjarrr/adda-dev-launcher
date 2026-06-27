---
name: project-ddd-architecture
description: DDD architectural patterns established in
metadata: 
  node_type: memory
  type: project
  originSessionId: a89184ba-37d5-4577-8885-2a4d295f4ff3
---

# DDD architecture — adda-dev-launcher Python package

Established during #58 (credential layer) design. These patterns govern all future issues.

**Why:** Early design assumed passive DTOs + helper functions. PO pushed for proper DDD: behavior lives with data, infrastructure is abstracted, consumers see only domain concepts.

**How to apply:** Every new module or domain concept should be evaluated against these patterns before planning. Raise deviations with PO.

---

## Active domain models

Domain models are `@dataclass(frozen=True)` — not passive Pydantic models. They own behavior alongside data. Pydantic models are DTOs only; they live at the parsing boundary and never contain active domain models.

## DTO naming convention

| Kind | Suffix | Example |
|---|---|---|
| Parsed from project TOML file | `*FileModel` | `ProjectFileModel`, `GitHubFileModel` |
| Parsed from `config.toml` section | `*ConfigModel` | `AnthropicConfigModel`, `DeepSeekConfigModel` |

`_from_file()` / `from_config()` classmethods on domain models own the DTO → domain translation. Config/app-level entities never instantiate domain models.

## Credential abstraction — `credentials.py`

`keyring` is infrastructure, hidden behind a `SecretStore` Protocol. Domain models never import `keyring` directly.

- `SecretStore` — Protocol: `get(service, key) -> str`
- `KeyringSecretStore` — concrete implementation
- `SecretError(AddaDevError)` — raised on missing secret
- `Secret` — Python ABC (not Pydantic): declares `_service: ClassVar[str]`, `secret_name: str`, `store: SecretStore`; provides concrete `get_secret()` → `self.store.get(self._service, self.secret_name)`

## Secret domain models

All credential-bearing domain models inherit `Secret`:

| Model | `_service` | Source |
|---|---|---|
| `GitHub` | `"adda-dev:github"` | project file `[github]` section |
| `AnthropicBackend` | `"adda-dev:anthropic"` | `config.toml` `[llm.anthropic]` |
| `DeepSeekBackend` | `"adda-dev:deepseek"` | `config.toml` `[llm.deepseek]` |

Store field pattern: `store: SecretStore = field(default_factory=KeyringSecretStore, repr=False, compare=False)` — production default, injectable in tests via constructor.

`get_secret()` is **always parameterless** — the store is never exposed to consumers.

## Keyring namespace convention

New format (Python launcher): `service="adda-dev:<vendor>"`, `username=<secret_name>`. Migration from bash launcher (old: `service=adda-dev account=<vendor> key=<name>`) via `/tmp/migrate-adda-secrets.sh`.

## Module layout

```
common → store / tmpfs / credentials → github / llm/* → app_config → project → cli
```

`llm/` is a subpackage (one module per vendor) for open/closed extension. `LlmConfig` lives in `llm/__init__.py` to avoid circular imports with `app_config.py`.

## Composition root

`cli.py` `run` command is the composition root: loads `AppConfig` + `Project`, calls `llm.resolve_backend(project.backend, config.llm)` to construct the backend domain model. No other layer instantiates domain models from config.

## Design process

Design questions were settled through Socratic discussion before entering plan mode — naming, abstraction boundaries, inheritance hierarchy, wiring strategy. This prevented the plan from encoding wrong decisions. Each question surfaced a real constraint; the plan was written only once the design was fully agreed.
