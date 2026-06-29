"""
Project domain entity.
"""

from dataclasses import dataclass

from ..common import AddaDevError
from .github import GitHub
from .llm import LlmBackend
from .tmpfs import TmpfsSizes


class ProjectNotFoundError(AddaDevError):
    """Raised when a project TOML file does not exist in the registry."""


@dataclass(frozen=True)
class Project:
    """Resolved project domain model; all fields are required and fully typed."""

    name: str
    github: GitHub
    image: str
    backend: LlmBackend
    tmpfs: TmpfsSizes
