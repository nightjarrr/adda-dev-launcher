"""
LLM provider domain models: enum and credential-bearing frozen dataclasses.
"""

import abc
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from .credentials import Secret, SecretSource


class LlmProvider(StrEnum):
    """Supported LLM providers."""

    anthropic = "anthropic"
    deepseek = "deepseek"


@dataclass(frozen=True)
class AnthropicProvider(Secret):
    """Anthropic credential and configuration domain model."""

    _service: ClassVar[str] = "adda-dev:anthropic"

    secret_name: str
    source: SecretSource


@dataclass(frozen=True)
class DeepSeekProvider(Secret):
    """DeepSeek credential and configuration domain model."""

    _service: ClassVar[str] = "adda-dev:deepseek"

    secret_name: str
    base_url: str
    model: str
    opus_model: str
    sonnet_model: str
    haiku_model: str
    subagent_model: str
    effort_level: str
    source: SecretSource


class ProviderRepository(abc.ABC):
    """Secondary port for retrieving provider aggregates by LlmProvider identity."""

    @abc.abstractmethod
    def get(self, provider: LlmProvider) -> AnthropicProvider | DeepSeekProvider: ...
