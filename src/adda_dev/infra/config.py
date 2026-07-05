"""
Application configuration: host settings DTOs and load_app_config().
"""

from enum import StrEnum

from ..common import StrictModel
from ..domain.tmpfs import TmpfsSizes
from .llm import LlmConfig
from .store import StorageArea, load_toml, resolve_storage_root

CONFIG_FILE_NAME = "config.toml"
DEFAULT_ENVOY_IMAGE = "envoyproxy/envoy:v1.33.14"


class ContainerEngineChoice(StrEnum):
    """Supported container engines."""

    docker = "docker"
    podman = "podman"


class ProjectDefaults(StrictModel):
    """Default values inherited by projects unless overridden in the project file."""

    tmpfs: TmpfsSizes = TmpfsSizes()


class AppConfig(StrictModel):
    """Host-level application configuration.

    All fields have defaults so a missing config.toml resolves to valid built-in values.
    """

    container_engine: ContainerEngineChoice = ContainerEngineChoice.docker
    envoy_image: str = DEFAULT_ENVOY_IMAGE
    llm: LlmConfig = LlmConfig()
    project_defaults: ProjectDefaults = ProjectDefaults()


def load_app_config() -> AppConfig:
    """Load AppConfig from config.toml; return defaults if the file is absent."""
    path = resolve_storage_root(StorageArea.config) / CONFIG_FILE_NAME
    if not path.exists():
        return AppConfig()
    return load_toml(path, AppConfig)
