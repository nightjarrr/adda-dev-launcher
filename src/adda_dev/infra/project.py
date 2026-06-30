"""
Project infrastructure: file schema DTOs, TomlProjectRepository, and helpers.
"""

from typing import Annotated

from pydantic import Field

from ..common import StrictModel
from ..domain.credentials import SecretSource
from ..domain.github import GitHub
from ..domain.llm import LlmBackend
from ..domain.project import Project, ProjectNotFoundError, ProjectRepository
from ..domain.tmpfs import TmpfsOverride
from .config import ProjectDefaults
from .store import StorageArea, load_toml, resolve_storage_root, validate_file_name

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


class TomlProjectRepository(ProjectRepository):
    """ProjectRepository adapter that reads projects from the TOML config store."""

    def __init__(self, defaults: ProjectDefaults, source: SecretSource) -> None:
        self._defaults = defaults
        self._source = source

    def get(self, name: str) -> Project:
        """Load a project from the registry by name.

        Raises:
            InvalidFileNameError: if name contains unsafe characters.
            ProjectNotFoundError: if the project TOML file does not exist.
            TomlParseError: if the file contains invalid TOML.
            SchemaValidationError: if the file fails schema validation.
        """
        path = resolve_storage_root(StorageArea.config) / PROJECTS_DIR_NAME / f"{validate_file_name(name)}.toml"
        if not path.exists():
            raise ProjectNotFoundError(f"Project {name!r} not found: {path} does not exist.")
        file = load_toml(path, ProjectFileModel)
        return Project(
            name=name,
            github=_build_github(file.github, self._source),
            image=file.image,
            backend=file.backend,
            tmpfs=self._defaults.tmpfs.with_override(file.tmpfs),
        )
