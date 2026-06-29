"""
DeepSeek backend configuration DTO and domain model.
"""

from dataclasses import dataclass, field
from typing import ClassVar

from ..common import StrictModel
from ..credentials import KeyringSecretStore, Secret, SecretStore


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
    store: SecretStore = field(default_factory=KeyringSecretStore, repr=False, compare=False)

    @classmethod
    def from_config(cls, config: DeepSeekConfigModel) -> DeepSeekBackend:
        """Construct a DeepSeekBackend from its config DTO."""
        return cls(
            secret_name=config.secret_name,
            base_url=config.base_url,
            model=config.model,
            opus_model=config.opus_model,
            sonnet_model=config.sonnet_model,
            haiku_model=config.haiku_model,
            subagent_model=config.subagent_model,
            effort_level=config.effort_level,
        )
