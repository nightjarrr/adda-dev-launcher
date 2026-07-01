"""
Session domain entity, error, and repository port.
"""

import abc
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..common import AddaDevError


class SessionNotFoundError(AddaDevError):
    """Raised when a session cannot be found in the repository."""


@dataclass(frozen=True)
class Session:
    """Running session entity; identified by session_id and owns its runtime directory lifecycle."""

    session_id: str
    project_name: str
    started_at: datetime
    runtime_dir: Path
    issue_id: int | None = None


class SessionRepository(abc.ABC):
    """Secondary port for creating and deleting Session aggregates."""

    @abc.abstractmethod
    def create(self, project_name: str, issue_id: int | None = None) -> Session: ...

    @abc.abstractmethod
    def delete(self, session: Session) -> None: ...
