"""
Tests for llm/anthropic.py: AnthropicConfigModel and AnthropicBackend.
"""

import pytest

from adda_dev.credentials import SecretError
from adda_dev.llm.anthropic import AnthropicBackend, AnthropicConfigModel
from tests.test_credentials import FakeSecretStore

# ---------------------------------------------------------------------------
# AnthropicConfigModel — defaults and validation
# ---------------------------------------------------------------------------


def test_anthropic_config_model_default_secret_name() -> None:
    cfg = AnthropicConfigModel()
    assert cfg.secret_name == "oauth"


def test_anthropic_config_model_override_secret_name() -> None:
    cfg = AnthropicConfigModel(secret_name="custom")
    assert cfg.secret_name == "custom"


def test_anthropic_config_model_extra_field_rejected() -> None:
    with pytest.raises(Exception):
        AnthropicConfigModel.model_validate({"secret_name": "oauth", "unknown": "x"})


# ---------------------------------------------------------------------------
# AnthropicBackend — from_config and get_secret
# ---------------------------------------------------------------------------


def test_anthropic_backend_from_config_uses_secret_name() -> None:
    cfg = AnthropicConfigModel(secret_name="my-oauth")
    backend = AnthropicBackend.from_config(cfg)
    assert backend.secret_name == "my-oauth"


def test_anthropic_backend_get_secret_returns_value() -> None:
    fake = FakeSecretStore({("adda-dev:anthropic", "oauth"): "claude-token"})
    cfg = AnthropicConfigModel()
    # Inject store by constructing directly since from_config uses default_factory.
    backend_with_store = AnthropicBackend(secret_name=cfg.secret_name, store=fake)
    assert backend_with_store.get_secret() == "claude-token"


def test_anthropic_backend_get_secret_raises_on_missing() -> None:
    fake = FakeSecretStore()
    backend = AnthropicBackend(secret_name="oauth", store=fake)
    with pytest.raises(SecretError):
        backend.get_secret()


def test_anthropic_backend_service_namespace() -> None:
    assert AnthropicBackend._service == "adda-dev:anthropic"


def test_anthropic_backend_frozen() -> None:
    backend = AnthropicBackend(secret_name="oauth")
    with pytest.raises(Exception):
        backend.secret_name = "changed"  # type: ignore[misc]
