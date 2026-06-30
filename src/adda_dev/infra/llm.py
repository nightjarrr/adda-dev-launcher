"""
LLM infrastructure: config DTOs and LlmConfigBackendRepository.
"""

from typing import assert_never

from ..common import StrictModel
from ..domain.credentials import SecretSource
from ..domain.llm import AnthropicBackend, BackendRepository, DeepSeekBackend, LlmBackend


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


class LlmConfig(StrictModel):
    """Registry of per-vendor LLM configuration DTOs."""

    anthropic: AnthropicConfigModel = AnthropicConfigModel()
    deepseek: DeepSeekConfigModel = DeepSeekConfigModel()


class LlmConfigBackendRepository(BackendRepository):
    """BackendRepository adapter that builds backend aggregates from LlmConfig."""

    def __init__(self, config: LlmConfig, source: SecretSource) -> None:
        self._config = config
        self._source = source

    def get(self, backend: LlmBackend) -> AnthropicBackend | DeepSeekBackend:
        """Dispatch a LlmBackend enum value to its domain model, constructed from config."""
        match backend:
            case LlmBackend.anthropic:
                return AnthropicBackend(secret_name=self._config.anthropic.secret_name, source=self._source)
            case LlmBackend.deepseek:
                c = self._config.deepseek
                return DeepSeekBackend(
                    secret_name=c.secret_name,
                    base_url=c.base_url,
                    model=c.model,
                    opus_model=c.opus_model,
                    sonnet_model=c.sonnet_model,
                    haiku_model=c.haiku_model,
                    subagent_model=c.subagent_model,
                    effort_level=c.effort_level,
                    source=self._source,
                )
        assert_never(backend)
