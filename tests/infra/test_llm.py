"""
Tests for infra/llm.py: AnthropicConfigModel, DeepSeekConfigModel, LlmConfigBackendRepository.
"""

from adda_dev.domain.llm import AnthropicBackend, DeepSeekBackend, LlmBackend
from adda_dev.infra.llm import (
    AnthropicConfigModel,
    DeepSeekConfigModel,
    LlmConfig,
    LlmConfigBackendRepository,
)
from tests.conftest import FakeSecretSource

# ---------------------------------------------------------------------------
# AnthropicConfigModel defaults
# ---------------------------------------------------------------------------


def test_anthropic_config_model_default_secret_name() -> None:
    cfg = AnthropicConfigModel()
    assert cfg.secret_name == "oauth"


def test_anthropic_config_model_custom_secret_name() -> None:
    cfg = AnthropicConfigModel(secret_name="my-oauth")
    assert cfg.secret_name == "my-oauth"


# ---------------------------------------------------------------------------
# DeepSeekConfigModel defaults
# ---------------------------------------------------------------------------


def test_deepseek_config_model_defaults() -> None:
    cfg = DeepSeekConfigModel()
    assert cfg.secret_name == "apikey"
    assert cfg.base_url == "https://api.deepseek.com/anthropic"
    assert cfg.model == "deepseek-v4-flash"
    assert cfg.opus_model == "deepseek-v4-pro[1m]"
    assert cfg.sonnet_model == "deepseek-v4-pro[1m]"
    assert cfg.haiku_model == "deepseek-v4-flash"
    assert cfg.subagent_model == "deepseek-v4-flash"
    assert cfg.effort_level == "max"


# ---------------------------------------------------------------------------
# LlmConfigBackendRepository.get — anthropic
# ---------------------------------------------------------------------------


def test_llm_config_backend_repository_anthropic_injects_source() -> None:
    fake = FakeSecretSource()
    repo = LlmConfigBackendRepository(LlmConfig(), fake)
    result = repo.get(LlmBackend.anthropic)
    assert isinstance(result, AnthropicBackend)
    assert result.source is fake


def test_llm_config_backend_repository_anthropic_uses_config_secret_name() -> None:
    fake = FakeSecretSource()
    cfg = LlmConfig.model_validate({"anthropic": {"secret_name": "custom-oauth"}})
    repo = LlmConfigBackendRepository(cfg, fake)
    result = repo.get(LlmBackend.anthropic)
    assert isinstance(result, AnthropicBackend)
    assert result.secret_name == "custom-oauth"


def test_llm_config_backend_repository_anthropic_default_secret_name() -> None:
    fake = FakeSecretSource()
    repo = LlmConfigBackendRepository(LlmConfig(), fake)
    result = repo.get(LlmBackend.anthropic)
    assert isinstance(result, AnthropicBackend)
    assert result.secret_name == "oauth"


# ---------------------------------------------------------------------------
# LlmConfigBackendRepository.get — deepseek
# ---------------------------------------------------------------------------


def test_llm_config_backend_repository_deepseek_injects_source() -> None:
    fake = FakeSecretSource()
    repo = LlmConfigBackendRepository(LlmConfig(), fake)
    result = repo.get(LlmBackend.deepseek)
    assert isinstance(result, DeepSeekBackend)
    assert result.source is fake


def test_llm_config_backend_repository_deepseek_maps_all_fields() -> None:
    fake = FakeSecretSource()
    cfg = LlmConfig.model_validate({"deepseek": {"secret_name": "ds-key"}})
    repo = LlmConfigBackendRepository(cfg, fake)
    result = repo.get(LlmBackend.deepseek)
    assert isinstance(result, DeepSeekBackend)
    assert result.secret_name == "ds-key"
    assert result.base_url == "https://api.deepseek.com/anthropic"
    assert result.model == "deepseek-v4-flash"
    assert result.opus_model == "deepseek-v4-pro[1m]"
    assert result.sonnet_model == "deepseek-v4-pro[1m]"
    assert result.haiku_model == "deepseek-v4-flash"
    assert result.subagent_model == "deepseek-v4-flash"
    assert result.effort_level == "max"


def test_llm_config_backend_repository_deepseek_uses_config() -> None:
    fake = FakeSecretSource()
    cfg = LlmConfig.model_validate({"deepseek": {"secret_name": "custom-ds"}})
    repo = LlmConfigBackendRepository(cfg, fake)
    result = repo.get(LlmBackend.deepseek)
    assert isinstance(result, DeepSeekBackend)
    assert result.secret_name == "custom-ds"
