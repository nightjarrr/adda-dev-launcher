"""
Tests for domain/llm.py: LlmBackend enum.
Tests for infra/llm.py: LlmConfig defaults, LlmConfigBackendRepository.
"""

import pytest

from adda_dev.domain.llm import AnthropicBackend, DeepSeekBackend, LlmBackend
from adda_dev.infra.llm import AnthropicConfigModel, DeepSeekConfigModel, LlmConfig, LlmConfigBackendRepository
from tests.conftest import FakeSecretSource

# ---------------------------------------------------------------------------
# LlmBackend enum
# ---------------------------------------------------------------------------


def test_llm_backend_members() -> None:
    assert LlmBackend.anthropic == "anthropic"
    assert LlmBackend.deepseek == "deepseek"


def test_llm_backend_from_string() -> None:
    assert LlmBackend("anthropic") is LlmBackend.anthropic
    assert LlmBackend("deepseek") is LlmBackend.deepseek


def test_llm_backend_invalid_raises() -> None:
    with pytest.raises(ValueError):
        LlmBackend("openai")


# ---------------------------------------------------------------------------
# LlmConfig — defaults
# ---------------------------------------------------------------------------


def test_llm_config_defaults() -> None:
    cfg = LlmConfig()
    assert isinstance(cfg.anthropic, AnthropicConfigModel)
    assert isinstance(cfg.deepseek, DeepSeekConfigModel)
    assert cfg.anthropic.secret_name == "oauth"
    assert cfg.deepseek.secret_name == "apikey"


def test_llm_config_extra_field_rejected() -> None:
    with pytest.raises(Exception):
        LlmConfig.model_validate({"anthropic": {}, "deepseek": {}, "openai": {}})


def test_llm_config_partial_override() -> None:
    cfg = LlmConfig.model_validate({"deepseek": {"secret_name": "ds-override"}})
    assert cfg.deepseek.secret_name == "ds-override"
    assert cfg.anthropic.secret_name == "oauth"


# ---------------------------------------------------------------------------
# LlmConfigBackendRepository
# ---------------------------------------------------------------------------


def test_llm_config_backend_repository_anthropic_returns_anthropic_backend() -> None:
    fake = FakeSecretSource()
    cfg = LlmConfig()
    result = LlmConfigBackendRepository(cfg, fake).get(LlmBackend.anthropic)
    assert isinstance(result, AnthropicBackend)
    assert result.secret_name == "oauth"


def test_llm_config_backend_repository_deepseek_returns_deepseek_backend() -> None:
    fake = FakeSecretSource()
    cfg = LlmConfig()
    result = LlmConfigBackendRepository(cfg, fake).get(LlmBackend.deepseek)
    assert isinstance(result, DeepSeekBackend)
    assert result.secret_name == "apikey"


def test_llm_config_backend_repository_anthropic_uses_config() -> None:
    fake = FakeSecretSource()
    cfg = LlmConfig.model_validate({"anthropic": {"secret_name": "custom-oauth"}})
    result = LlmConfigBackendRepository(cfg, fake).get(LlmBackend.anthropic)
    assert isinstance(result, AnthropicBackend)
    assert result.secret_name == "custom-oauth"


def test_llm_config_backend_repository_deepseek_uses_config() -> None:
    fake = FakeSecretSource()
    cfg = LlmConfig.model_validate({"deepseek": {"secret_name": "custom-ds"}})
    result = LlmConfigBackendRepository(cfg, fake).get(LlmBackend.deepseek)
    assert isinstance(result, DeepSeekBackend)
    assert result.secret_name == "custom-ds"
