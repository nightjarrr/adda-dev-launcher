"""
LLM backend sub-domain: enum, per-vendor config models, and the backends registry.
"""

from enum import StrEnum

from .common import StrictModel


class LlmBackend(StrEnum):
    """Supported LLM backends."""

    anthropic = "anthropic"
    deepseek = "deepseek"


class LlmBackendConfig(StrictModel):
    """Base configuration for an LLM backend; every vendor must supply a keyring key."""

    keyring_key: str


class AnthropicBackendConfig(LlmBackendConfig):
    """Anthropic backend configuration."""

    keyring_key: str = "oauth"


class DeepSeekBackendConfig(LlmBackendConfig):
    """DeepSeek backend configuration with model and API defaults from the Bash launcher."""

    keyring_key: str = "apikey"
    base_url: str = "https://api.deepseek.com/anthropic"
    model: str = "deepseek-v4-flash"
    opus_model: str = "deepseek-v4-pro[1m]"
    sonnet_model: str = "deepseek-v4-pro[1m]"
    haiku_model: str = "deepseek-v4-flash"
    subagent_model: str = "deepseek-v4-flash"
    effort_level: str = "max"


class Backends(StrictModel):
    """Registry of per-vendor backend configurations."""

    anthropic: AnthropicBackendConfig = AnthropicBackendConfig()
    deepseek: DeepSeekBackendConfig = DeepSeekBackendConfig()
