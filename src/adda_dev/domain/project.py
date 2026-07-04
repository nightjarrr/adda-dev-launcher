"""
Project domain entity.
"""

import abc
from dataclasses import dataclass

from ..common import AddaDevError
from .github import GitHub
from .llm import LlmProvider
from .tmpfs import TmpfsSizes


class ProjectNotFoundError(AddaDevError):
    """Raised when a project TOML file does not exist in the registry."""


class ProjectRepository(abc.ABC):
    """Secondary port for retrieving Project aggregates by name."""

    @abc.abstractmethod
    def get(self, name: str) -> Project: ...


@dataclass(frozen=True)
class Project:
    """Resolved project domain model; all fields are required and fully typed."""

    name: str
    github: GitHub
    image: str
    provider: LlmProvider
    tmpfs: TmpfsSizes
