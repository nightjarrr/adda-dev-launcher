"""
Session infrastructure: filesystem-backed session repository.
"""

import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..common import StrictModel
from ..domain.session import Session, SessionRepository
from .store import StorageArea, resolve_storage_root, write_toml


class SessionFileModel(StrictModel):
    """Serialized form of session.toml. runtime_dir is derived from path on read."""

    session_id: str
    project_name: str
    started_at: datetime
    issue_id: int | None = None


class FsSessionRepository(SessionRepository):
    """SessionRepository adapter that stores session state in the XDG runtime directory."""

    def __init__(self, runtime_base: Path | None = None) -> None:
        self._runtime_base = runtime_base or resolve_storage_root(StorageArea.runtime)

    def create(self, project_name: str, issue_id: int | None = None) -> Session:
        session_id = f"session-{uuid.uuid4()}"
        runtime_dir = self._runtime_base / session_id
        runtime_dir.mkdir(parents=True, mode=0o700)
        started_at = datetime.now(UTC)
        write_toml(
            runtime_dir / "session.toml",
            SessionFileModel(
                session_id=session_id,
                project_name=project_name,
                started_at=started_at,
                issue_id=issue_id,
            ),
        )
        return Session(
            session_id=session_id,
            project_name=project_name,
            started_at=started_at,
            runtime_dir=runtime_dir,
            issue_id=issue_id,
        )

    def terminate(self, session: Session) -> None:
        shutil.rmtree(session.runtime_dir, ignore_errors=True)
