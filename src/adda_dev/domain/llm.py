"""
LLM backend domain models: enum and credential-bearing frozen dataclasses.
"""

import abc
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from .credentials import Secret, SecretSource


class LlmBackend(StrEnum):
    """Supported LLM backends."""

    anthropic = "anthropic"
    deepseek = "deepseek"


@dataclass(frozen=True)
class AnthropicBackend(Secret):
    """Anthropic credential and configuration domain model."""

    _service: ClassVar[str] = "adda-dev:anthropic"

    secret_name: str
    source: SecretSource


@dataclass(frozen=True)
class DeepSeekBackend(Secret):
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


class BackendRepository(abc.ABC):
    """Secondary port for retrieving backend aggregates by LlmBackend identity."""

    @abc.abstractmethod
    def get(self, backend: LlmBackend) -> AnthropicBackend | DeepSeekBackend: ...
