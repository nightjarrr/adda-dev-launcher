"""
Project infrastructure: file schema DTOs, load_project(), and helpers.
"""

from pathlib import Path
from typing import Annotated

from pydantic import Field

from ..common import StrictModel
from ..domain.credentials import SecretSource
from ..domain.github import GitHub
from ..domain.llm import LlmBackend
from ..domain.project import Project, ProjectNotFoundError
from ..domain.tmpfs import TmpfsOverride
from .config import ProjectDefaults
from .store import load_toml, resolve_config_dir, validate_file_name

PROJECTS_DIR_NAME = "projects"

# GitHub owner/repo name: letters, digits, hyphens, underscores, dots.
_GH_NAME_PATTERN = r"^[A-Za-z0-9._-]+$"


class GitHubFileModel(StrictModel):
    """DTO for the [github] section of a project TOML file."""

    owner: Annotated[str, Field(pattern=_GH_NAME_PATTERN)]
    repo: Annotated[str, Field(pattern=_GH_NAME_PATTERN)]
    secret_name: str


class ProjectFileModel(StrictModel):
    """Serialized form of a project file; carries optional tmpfs overrides."""

    github: GitHubFileModel
    image: str
    backend: LlmBackend
    tmpfs: TmpfsOverride | None = None


def _build_github(file: GitHubFileModel, source: SecretSource) -> GitHub:
    return GitHub(owner=file.owner, repo=file.repo, secret_name=file.secret_name, source=source)


def load_project(name: str, defaults: ProjectDefaults, source: SecretSource, config_dir: Path | None = None) -> Project:
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
    return Project(
        name=name,
        github=_build_github(file.github, source),
        image=file.image,
        backend=file.backend,
        tmpfs=defaults.tmpfs.with_override(file.tmpfs),
    )
