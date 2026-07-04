"""
Tests for domain/llm.py: LlmProvider enum.
Tests for infra/llm.py: LlmConfig defaults, LlmConfigProviderRepository.
"""

import pytest

from adda_dev.domain.llm import AnthropicProvider, DeepSeekProvider, LlmProvider
from adda_dev.infra.llm import AnthropicConfigModel, DeepSeekConfigModel, LlmConfig, LlmConfigProviderRepository
from tests.conftest import FakeSecretSource

# ---------------------------------------------------------------------------
# LlmProvider enum
# ---------------------------------------------------------------------------


def test_llm_backend_members() -> None:
    assert LlmProvider.anthropic == "anthropic"
    assert LlmProvider.deepseek == "deepseek"


def test_llm_backend_from_string() -> None:
    assert LlmProvider("anthropic") is LlmProvider.anthropic
    assert LlmProvider("deepseek") is LlmProvider.deepseek


def test_llm_backend_invalid_raises() -> None:
    with pytest.raises(ValueError):
        LlmProvider("openai")


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
# LlmConfigProviderRepository
# ---------------------------------------------------------------------------


def test_llm_config_backend_repository_anthropic_returns_anthropic_backend() -> None:
    fake = FakeSecretSource()
    cfg = LlmConfig()
    result = LlmConfigProviderRepository(cfg, fake).get(LlmProvider.anthropic)
    assert isinstance(result, AnthropicProvider)
    assert result.secret_name == "oauth"


def test_llm_config_backend_repository_deepseek_returns_deepseek_backend() -> None:
    fake = FakeSecretSource()
    cfg = LlmConfig()
    result = LlmConfigProviderRepository(cfg, fake).get(LlmProvider.deepseek)
    assert isinstance(result, DeepSeekProvider)
    assert result.secret_name == "apikey"


def test_llm_config_backend_repository_anthropic_uses_config() -> None:
    fake = FakeSecretSource()
    cfg = LlmConfig.model_validate({"anthropic": {"secret_name": "custom-oauth"}})
    result = LlmConfigProviderRepository(cfg, fake).get(LlmProvider.anthropic)
    assert isinstance(result, AnthropicProvider)
    assert result.secret_name == "custom-oauth"


def test_llm_config_backend_repository_deepseek_uses_config() -> None:
    fake = FakeSecretSource()
    cfg = LlmConfig.model_validate({"deepseek": {"secret_name": "custom-ds"}})
    result = LlmConfigProviderRepository(cfg, fake).get(LlmProvider.deepseek)
    assert isinstance(result, DeepSeekProvider)
    assert result.secret_name == "custom-ds"
