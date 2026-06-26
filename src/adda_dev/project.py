"""
Project domain entity: file schema, resolution, and load from the registry.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from pydantic import Field

from .app_config import ProjectDefaults
from .common import AddaDevError, StrictModel
from .llm_backend import LlmBackend
from .store import load_toml, projects_dir, resolve_config_dir, validate_file_name
from .tmpfs import TmpfsOverride, TmpfsSizes

# GitHub owner/repo name: letters, digits, hyphens, underscores, dots.
_GH_NAME_PATTERN = r"^[A-Za-z0-9._-]+$"


class ProjectNotFoundError(AddaDevError):
    """Raised when a project TOML file does not exist in the registry."""


class ProjectFileModel(StrictModel):
    """Serialized form of a project file; carries optional tmpfs overrides."""

    owner: Annotated[str, Field(pattern=_GH_NAME_PATTERN)]
    repo: Annotated[str, Field(pattern=_GH_NAME_PATTERN)]
    image: str
    github_keyring_key: str
    backend: LlmBackend
    tmpfs: TmpfsOverride | None = None


@dataclass(frozen=True)
class Project:
    """Resolved project domain model; all fields are required and fully typed."""

    name: str
    owner: str
    repo: str
    image: str
    github_keyring_key: str
    backend: LlmBackend
    tmpfs: TmpfsSizes

    # Private methods

    @classmethod
    def _from_file(cls, name: str, file: ProjectFileModel, defaults: ProjectDefaults) -> Project:
        """Resolve a ProjectFileModel against ProjectDefaults into a fully-resolved Project."""
        return cls(
            name=name,
            owner=file.owner,
            repo=file.repo,
            image=file.image,
            github_keyring_key=file.github_keyring_key,
            backend=file.backend,
            tmpfs=defaults.tmpfs.with_override(file.tmpfs),
        )

    # Public methods

    @classmethod
    def load(cls, name: str, defaults: ProjectDefaults, config_dir: Path | None = None) -> Project:
        """Load a project from the registry by name.

        Raises:
            InvalidFileNameError: if name contains unsafe characters.
            ProjectNotFoundError: if the project TOML file does not exist.
            TomlParseError: if the file contains invalid TOML.
            SchemaValidationError: if the file fails schema validation.
        """
        cd = config_dir if config_dir is not None else resolve_config_dir()
        path = projects_dir(cd) / f"{validate_file_name(name)}.toml"
        if not path.exists():
            raise ProjectNotFoundError(f"Project {name!r} not found: {path} does not exist.")
        file = load_toml(path, ProjectFileModel)
        return cls._from_file(name, file, defaults)
