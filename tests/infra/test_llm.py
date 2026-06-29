"""
Tests for infra/llm.py: _build_anthropic_backend, _build_deepseek_backend, resolve_backend.
"""

from adda_dev.domain.llm import AnthropicBackend, DeepSeekBackend, LlmBackend
from adda_dev.infra.llm import (
    AnthropicConfigModel,
    DeepSeekConfigModel,
    LlmConfig,
    _build_anthropic_backend,
    _build_deepseek_backend,
    resolve_backend,
)
from tests.conftest import FakeSecretSource

# ---------------------------------------------------------------------------
# _build_anthropic_backend
# ---------------------------------------------------------------------------


def test_build_anthropic_backend_uses_config_secret_name() -> None:
    fake = FakeSecretSource()
    cfg = AnthropicConfigModel(secret_name="my-oauth")
    backend = _build_anthropic_backend(cfg, fake)
    assert isinstance(backend, AnthropicBackend)
    assert backend.secret_name == "my-oauth"
    assert backend.source is fake


def test_build_anthropic_backend_default_secret_name() -> None:
    fake = FakeSecretSource()
    backend = _build_anthropic_backend(AnthropicConfigModel(), fake)
    assert backend.secret_name == "oauth"


# ---------------------------------------------------------------------------
# _build_deepseek_backend
# ---------------------------------------------------------------------------


def test_build_deepseek_backend_maps_all_fields() -> None:
    fake = FakeSecretSource()
    cfg = DeepSeekConfigModel(secret_name="ds-key")
    backend = _build_deepseek_backend(cfg, fake)
    assert isinstance(backend, DeepSeekBackend)
    assert backend.secret_name == "ds-key"
    assert backend.base_url == "https://api.deepseek.com/anthropic"
    assert backend.model == "deepseek-v4-flash"
    assert backend.opus_model == "deepseek-v4-pro[1m]"
    assert backend.sonnet_model == "deepseek-v4-pro[1m]"
    assert backend.haiku_model == "deepseek-v4-flash"
    assert backend.subagent_model == "deepseek-v4-flash"
    assert backend.effort_level == "max"
    assert backend.source is fake


def test_build_deepseek_backend_default_config() -> None:
    fake = FakeSecretSource()
    backend = _build_deepseek_backend(DeepSeekConfigModel(), fake)
    assert backend.secret_name == "apikey"


# ---------------------------------------------------------------------------
# resolve_backend — delegates to correct builder
# ---------------------------------------------------------------------------


def test_resolve_backend_anthropic_injects_source() -> None:
    fake = FakeSecretSource()
    result = resolve_backend(LlmBackend.anthropic, LlmConfig(), fake)
    assert isinstance(result, AnthropicBackend)
    assert result.source is fake


def test_resolve_backend_deepseek_injects_source() -> None:
    fake = FakeSecretSource()
    result = resolve_backend(LlmBackend.deepseek, LlmConfig(), fake)
    assert isinstance(result, DeepSeekBackend)
    assert result.source is fake


def test_resolve_backend_anthropic_uses_llm_config() -> None:
    fake = FakeSecretSource()
    cfg = LlmConfig.model_validate({"anthropic": {"secret_name": "custom-oauth"}})
    result = resolve_backend(LlmBackend.anthropic, cfg, fake)
    assert isinstance(result, AnthropicBackend)
    assert result.secret_name == "custom-oauth"


def test_resolve_backend_deepseek_uses_llm_config() -> None:
    fake = FakeSecretSource()
    cfg = LlmConfig.model_validate({"deepseek": {"secret_name": "custom-ds"}})
    result = resolve_backend(LlmBackend.deepseek, cfg, fake)
    assert isinstance(result, DeepSeekBackend)
    assert result.secret_name == "custom-ds"
