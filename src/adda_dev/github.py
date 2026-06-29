"""
GitHub identity DTO and domain model.
"""

from dataclasses import dataclass, field
from typing import Annotated, ClassVar

from pydantic import Field

from .common import StrictModel
from .credentials import KeyringSecretStore, Secret, SecretStore

# GitHub owner/repo name: letters, digits, hyphens, underscores, dots.
_GH_NAME_PATTERN = r"^[A-Za-z0-9._-]+$"


class GitHubFileModel(StrictModel):
    """DTO for the [github] section of a project TOML file."""

    owner: Annotated[str, Field(pattern=_GH_NAME_PATTERN)]
    repo: Annotated[str, Field(pattern=_GH_NAME_PATTERN)]
    secret_name: str


@dataclass(frozen=True)
class GitHub(Secret):
    """GitHub identity and credential retrieval domain model."""

    _service: ClassVar[str] = "adda-dev:github"

    owner: str
    repo: str
    secret_name: str
    store: SecretStore = field(default_factory=KeyringSecretStore, repr=False, compare=False)
