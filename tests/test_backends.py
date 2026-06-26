"""
Tests for backends.py: LlmBackend enum, per-vendor configs, Backends registry.
"""

import pytest

from adda_dev.backends import (
    AnthropicBackendConfig,
    Backends,
    DeepSeekBackendConfig,
    LlmBackend,
    LlmBackendConfig,
)

# ---------------------------------------------------------------------------
# LlmBackend enum
# ---------------------------------------------------------------------------


def test_llm_backend_members() -> None:
    assert LlmBackend.anthropic == "anthropic"
    assert LlmBackend.deepseek == "deepseek"


def test_llm_backend_from_string() -> None:
    assert LlmBackend("anthropic") is LlmBackend.anthropic
    assert LlmBackend("deepseek") is LlmBackend.deepseek


# ---------------------------------------------------------------------------
# LlmBackendConfig — base requires keyring_key
# ---------------------------------------------------------------------------


def test_llm_backend_config_requires_keyring_key() -> None:
    with pytest.raises(Exception):
        LlmBackendConfig.model_validate({})


def test_llm_backend_config_accepts_keyring_key() -> None:
    cfg = LlmBackendConfig(keyring_key="my-key")
    assert cfg.keyring_key == "my-key"


# ---------------------------------------------------------------------------
# AnthropicBackendConfig — defaults
# ---------------------------------------------------------------------------


def test_anthropic_backend_config_default_keyring_key() -> None:
    cfg = AnthropicBackendConfig()
    assert cfg.keyring_key == "oauth"


def test_anthropic_backend_config_override_keyring_key() -> None:
    cfg = AnthropicBackendConfig(keyring_key="custom")
    assert cfg.keyring_key == "custom"


def test_anthropic_backend_config_extra_field_rejected() -> None:
    with pytest.raises(Exception):
        AnthropicBackendConfig.model_validate({"keyring_key": "oauth", "unknown": "value"})


# ---------------------------------------------------------------------------
# DeepSeekBackendConfig — defaults verbatim from adda-dev.sh
# ---------------------------------------------------------------------------


def test_deepseek_backend_config_defaults() -> None:
    cfg = DeepSeekBackendConfig()
    assert cfg.keyring_key == "apikey"
    assert cfg.base_url == "https://api.deepseek.com/anthropic"
    assert cfg.model == "deepseek-v4-flash"
    assert cfg.opus_model == "deepseek-v4-pro[1m]"
    assert cfg.sonnet_model == "deepseek-v4-pro[1m]"
    assert cfg.haiku_model == "deepseek-v4-flash"
    assert cfg.subagent_model == "deepseek-v4-flash"
    assert cfg.effort_level == "max"


def test_deepseek_backend_config_override_keyring_key() -> None:
    cfg = DeepSeekBackendConfig(keyring_key="ds-key")
    assert cfg.keyring_key == "ds-key"


def test_deepseek_backend_config_extra_field_rejected() -> None:
    with pytest.raises(Exception):
        DeepSeekBackendConfig.model_validate({"unknown": "x"})


# ---------------------------------------------------------------------------
# Backends registry — defaults
# ---------------------------------------------------------------------------


def test_backends_defaults() -> None:
    backends = Backends()
    assert isinstance(backends.anthropic, AnthropicBackendConfig)
    assert isinstance(backends.deepseek, DeepSeekBackendConfig)
    assert backends.anthropic.keyring_key == "oauth"
    assert backends.deepseek.keyring_key == "apikey"


def test_backends_extra_field_rejected() -> None:
    with pytest.raises(Exception):
        Backends.model_validate({"anthropic": {}, "deepseek": {}, "openai": {}})


def test_backends_partial_override_from_toml() -> None:
    # Simulates what happens when only deepseek.keyring_key is overridden.
    data = {"deepseek": {"keyring_key": "ds-override"}}
    backends = Backends.model_validate(data)
    assert backends.deepseek.keyring_key == "ds-override"
    # anthropic retains its default
    assert backends.anthropic.keyring_key == "oauth"
