"""
Tests for domain/llm.py: AnthropicBackend.
Tests for infra/llm.py: AnthropicConfigModel.
"""

import pytest

from adda_dev.domain.credentials import SecretError
from adda_dev.domain.llm import AnthropicBackend
from adda_dev.infra.llm import AnthropicConfigModel
from tests.conftest import FakeSecretSource

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
# AnthropicBackend — construction and get_secret
# ---------------------------------------------------------------------------


def test_anthropic_backend_get_secret_returns_value() -> None:
    fake = FakeSecretSource({("adda-dev:anthropic", "oauth"): "claude-token"})
    backend = AnthropicBackend(secret_name="oauth", source=fake)
    assert backend.get_secret() == "claude-token"


def test_anthropic_backend_get_secret_raises_on_missing() -> None:
    fake = FakeSecretSource()
    backend = AnthropicBackend(secret_name="oauth", source=fake)
    with pytest.raises(SecretError):
        backend.get_secret()


def test_anthropic_backend_service_namespace() -> None:
    assert AnthropicBackend._service == "adda-dev:anthropic"


def test_anthropic_backend_frozen() -> None:
    fake = FakeSecretSource()
    backend = AnthropicBackend(secret_name="oauth", source=fake)
    with pytest.raises(Exception):
        backend.secret_name = "changed"  # type: ignore[misc]
