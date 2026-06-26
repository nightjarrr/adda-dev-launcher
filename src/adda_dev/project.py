"""
Project domain entity: file schema, resolution, and load from the registry.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from pydantic import Field

from .app_config import ProjectDefaults
from .backends import LlmBackend
from .common import AddaDevError, StrictModel
from .store import load_toml, project_file, resolve_config_dir
from .tmpfs import TmpfsOverride, TmpfsSizes

# GitHub owner/repo name: letters, digits, hyphens, underscores, dots.
_GH_NAME_PATTERN = r"^[A-Za-z0-9._-]+$"


class ProjectNotFoundError(AddaDevError):
    """Raised when a project TOML file does not exist in the registry."""


class ProjectFile(StrictModel):
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

    # Public methods

    @classmethod
    def from_file(cls, name: str, file: ProjectFile, defaults: ProjectDefaults) -> Project:
        """Resolve a ProjectFile against ProjectDefaults into a fully-resolved Project.

        Each tmpfs field is taken from the project's override if non-None, otherwise
        inherited from the defaults.
        """
        base = defaults.tmpfs
        override = file.tmpfs

        if override is None:
            resolved_tmpfs = base
        else:
            resolved_tmpfs = TmpfsSizes(
                home=override.home if override.home is not None else base.home,
                workspace=override.workspace if override.workspace is not None else base.workspace,
                tmp=override.tmp if override.tmp is not None else base.tmp,
            )

        return cls(
            name=name,
            owner=file.owner,
            repo=file.repo,
            image=file.image,
            github_keyring_key=file.github_keyring_key,
            backend=file.backend,
            tmpfs=resolved_tmpfs,
        )

    @classmethod
    def load(cls, name: str, defaults: ProjectDefaults, config_dir: Path | None = None) -> Project:
        """Load a project from the registry by name.

        Raises:
            InvalidProjectNameError: if name contains unsafe characters.
            ProjectNotFoundError: if the project TOML file does not exist.
            TomlParseError: if the file contains invalid TOML.
            SchemaValidationError: if the file fails schema validation.
        """
        cd = config_dir if config_dir is not None else resolve_config_dir()
        # project_file validates the name and raises InvalidProjectNameError if invalid.
        path = project_file(cd, name)
        if not path.exists():
            raise ProjectNotFoundError(f"Project {name!r} not found: {path} does not exist.")
        file = load_toml(path, ProjectFile)
        return cls.from_file(name, file, defaults)
