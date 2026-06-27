"""
Anthropic backend configuration DTO and domain model.
"""

from dataclasses import dataclass, field
from typing import ClassVar

from ..common import StrictModel
from ..credentials import KeyringSecretStore, Secret, SecretStore


class AnthropicConfigModel(StrictModel):
    """Configuration DTO for the [llm.anthropic] config.toml section."""

    secret_name: str = "oauth"


@dataclass(frozen=True)
class AnthropicBackend(Secret):
    """Anthropic credential and configuration domain model."""

    _service: ClassVar[str] = "adda-dev:anthropic"

    secret_name: str
    store: SecretStore = field(default_factory=KeyringSecretStore, repr=False, compare=False)

    @classmethod
    def from_config(cls, config: AnthropicConfigModel) -> AnthropicBackend:
        """Construct an AnthropicBackend from its config DTO."""
        return cls(secret_name=config.secret_name)
