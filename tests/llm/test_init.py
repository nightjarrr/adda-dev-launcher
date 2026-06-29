"""
Tests for llm/__init__.py: LlmBackend enum, LlmConfig defaults, resolve_backend().
"""

import pytest

from adda_dev.llm import LlmBackend, LlmConfig, resolve_backend
from adda_dev.llm.anthropic import AnthropicBackend, AnthropicConfigModel
from adda_dev.llm.deepseek import DeepSeekBackend, DeepSeekConfigModel

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
# resolve_backend
# ---------------------------------------------------------------------------


def test_resolve_backend_anthropic_returns_anthropic_backend() -> None:
    cfg = LlmConfig()
    result = resolve_backend(LlmBackend.anthropic, cfg)
    assert isinstance(result, AnthropicBackend)
    assert result.secret_name == "oauth"


def test_resolve_backend_deepseek_returns_deepseek_backend() -> None:
    cfg = LlmConfig()
    result = resolve_backend(LlmBackend.deepseek, cfg)
    assert isinstance(result, DeepSeekBackend)
    assert result.secret_name == "apikey"


def test_resolve_backend_anthropic_uses_config() -> None:
    cfg = LlmConfig.model_validate({"anthropic": {"secret_name": "custom-oauth"}})
    result = resolve_backend(LlmBackend.anthropic, cfg)
    assert isinstance(result, AnthropicBackend)
    assert result.secret_name == "custom-oauth"


def test_resolve_backend_deepseek_uses_config() -> None:
    cfg = LlmConfig.model_validate({"deepseek": {"secret_name": "custom-ds"}})
    result = resolve_backend(LlmBackend.deepseek, cfg)
    assert isinstance(result, DeepSeekBackend)
    assert result.secret_name == "custom-ds"
