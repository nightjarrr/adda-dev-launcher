"""
Project domain entity: file schema, resolution, and load from the registry.
"""

from dataclasses import dataclass
from pathlib import Path

from .app_config import ProjectDefaults
from .common import AddaDevError, StrictModel
from .github import GitHub, GitHubFileModel
from .llm import LlmBackend
from .store import load_toml, resolve_config_dir, validate_file_name
from .tmpfs import TmpfsOverride, TmpfsSizes

PROJECTS_DIR_NAME = "projects"


class ProjectNotFoundError(AddaDevError):
    """Raised when a project TOML file does not exist in the registry."""


class ProjectFileModel(StrictModel):
    """Serialized form of a project file; carries optional tmpfs overrides."""

    github: GitHubFileModel
    image: str
    backend: LlmBackend
    tmpfs: TmpfsOverride | None = None


@dataclass(frozen=True)
class Project:
    """Resolved project domain model; all fields are required and fully typed."""

    name: str
    github: GitHub
    image: str
    backend: LlmBackend
    tmpfs: TmpfsSizes

    # Private methods

    @classmethod
    def _from_file(cls, name: str, file: ProjectFileModel, defaults: ProjectDefaults) -> Project:
        """Resolve a ProjectFileModel against ProjectDefaults into a fully-resolved Project."""
        return cls(
            name=name,
            github=GitHub(owner=file.github.owner, repo=file.github.repo, secret_name=file.github.secret_name),
            image=file.image,
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
        path = cd / PROJECTS_DIR_NAME / f"{validate_file_name(name)}.toml"
        if not path.exists():
            raise ProjectNotFoundError(f"Project {name!r} not found: {path} does not exist.")
        file = load_toml(path, ProjectFileModel)
        return cls._from_file(name, file, defaults)
