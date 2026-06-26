"""
Application configuration entity: host settings, backend registry, and project defaults.
"""

from enum import StrEnum
from pathlib import Path

from .backends import Backends
from .common import StrictModel
from .store import app_config_file, load_toml, resolve_config_dir
from .tmpfs import TmpfsSizes


class ContainerEngine(StrEnum):
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

    container_engine: ContainerEngine = ContainerEngine.docker
    envoy_image: str = "envoyproxy/envoy:v1.33.14"
    tmux_config_path: Path | None = None
    backends: Backends = Backends()
    project_defaults: ProjectDefaults = ProjectDefaults()

    # Public methods

    @classmethod
    def load(cls, config_dir: Path | None = None) -> AppConfig:
        """Load AppConfig from config.toml; return defaults if the file is absent."""
        cd = config_dir if config_dir is not None else resolve_config_dir()
        path = app_config_file(cd)
        if not path.exists():
            return cls()
        return load_toml(path, cls)
