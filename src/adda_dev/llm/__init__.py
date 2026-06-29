"""
LLM backend sub-domain: enum, config registry DTO, and backend resolution.
"""

from enum import StrEnum
from typing import assert_never

from ..common import StrictModel
from .anthropic import AnthropicBackend, AnthropicConfigModel
from .deepseek import DeepSeekBackend, DeepSeekConfigModel


class LlmBackend(StrEnum):
    """Supported LLM backends."""

    anthropic = "anthropic"
    deepseek = "deepseek"


class LlmConfig(StrictModel):
    """Registry of per-vendor LLM configuration DTOs."""

    anthropic: AnthropicConfigModel = AnthropicConfigModel()
    deepseek: DeepSeekConfigModel = DeepSeekConfigModel()


def resolve_backend(backend: LlmBackend, config: LlmConfig) -> AnthropicBackend | DeepSeekBackend:
    """Dispatch a LlmBackend enum value to its domain model, constructed from config."""
    match backend:
        case LlmBackend.anthropic:
            return AnthropicBackend.from_config(config.anthropic)
        case LlmBackend.deepseek:
            return DeepSeekBackend.from_config(config.deepseek)
    assert_never(backend)
