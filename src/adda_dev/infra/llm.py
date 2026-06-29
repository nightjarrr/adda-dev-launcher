"""
LLM infrastructure: config DTOs, backend factory functions, and resolve_backend().
"""

from typing import assert_never

from ..common import StrictModel
from ..domain.credentials import SecretSource
from ..domain.llm import AnthropicBackend, DeepSeekBackend, LlmBackend


class AnthropicConfigModel(StrictModel):
    """Configuration DTO for the [llm.anthropic] config.toml section."""

    secret_name: str = "oauth"


class DeepSeekConfigModel(StrictModel):
    """Configuration DTO for the [llm.deepseek] config.toml section."""

    secret_name: str = "apikey"
    base_url: str = "https://api.deepseek.com/anthropic"
    model: str = "deepseek-v4-flash"
    opus_model: str = "deepseek-v4-pro[1m]"
    sonnet_model: str = "deepseek-v4-pro[1m]"
    haiku_model: str = "deepseek-v4-flash"
    subagent_model: str = "deepseek-v4-flash"
    effort_level: str = "max"


def _build_anthropic_backend(config: AnthropicConfigModel, source: SecretSource) -> AnthropicBackend:
    return AnthropicBackend(secret_name=config.secret_name, source=source)


def _build_deepseek_backend(config: DeepSeekConfigModel, source: SecretSource) -> DeepSeekBackend:
    return DeepSeekBackend(
        secret_name=config.secret_name,
        base_url=config.base_url,
        model=config.model,
        opus_model=config.opus_model,
        sonnet_model=config.sonnet_model,
        haiku_model=config.haiku_model,
        subagent_model=config.subagent_model,
        effort_level=config.effort_level,
        source=source,
    )


class LlmConfig(StrictModel):
    """Registry of per-vendor LLM configuration DTOs."""

    anthropic: AnthropicConfigModel = AnthropicConfigModel()
    deepseek: DeepSeekConfigModel = DeepSeekConfigModel()


def resolve_backend(backend: LlmBackend, config: LlmConfig, source: SecretSource) -> AnthropicBackend | DeepSeekBackend:
    """Dispatch a LlmBackend enum value to its domain model, constructed from config."""
    match backend:
        case LlmBackend.anthropic:
            return _build_anthropic_backend(config.anthropic, source)
        case LlmBackend.deepseek:
            return _build_deepseek_backend(config.deepseek, source)
    assert_never(backend)
