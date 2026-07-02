"""
Session infrastructure: filesystem-backed session repository, Direct window, and Direct session manager.
"""

import shutil
import uuid
from datetime import UTC, datetime

from ..common import Output, StrictModel
from ..domain.container import ContainerEngine
from ..domain.contract import ContractTranslator
from ..domain.process import ProcessHandle, ProcessRunner
from ..domain.session import Session, SessionRepository
from ..domain.session_manager import SessionManager, Window
from .process import DefaultRunner
from .store import StorageArea, resolve_storage_root, write_toml


class SessionFileModel(StrictModel):
    """Serialized form of session.toml. runtime_dir is derived from path on read."""

    session_id: str
    project_name: str
    started_at: datetime
    issue_id: int | None = None


class FsSessionRepository(SessionRepository):
    """SessionRepository adapter that stores session state in the XDG runtime directory."""

    def __init__(self) -> None:
        self._runtime_base = resolve_storage_root(StorageArea.runtime)

    def create(self, project_name: str, issue_id: int | None = None) -> Session:
        session_id = f"adda-dev-session-{uuid.uuid4().hex[:8]}"
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

    def delete(self, session: Session) -> None:
        shutil.rmtree(session.runtime_dir, ignore_errors=True)


class DirectWindow(Window):
    """Window implementation that runs a subprocess with inherited stdio."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self._handle: ProcessHandle | None = None

    def open(self, cmd: list[str], env: dict[str, str] | None = None) -> None:
        self._handle = DefaultRunner().run(cmd, env)

    def attach(self) -> None:
        assert self._handle is not None
        self._handle.wait()

    def close(self) -> None:
        pass  # process already exited when attach() returned; no teardown needed


class DirectSessionManager(SessionManager):
    """SessionManager that runs commands directly in the current terminal (no tmux)."""

    def __init__(
        self,
        session_repo: SessionRepository,
        translator: ContractTranslator,
        engine: ContainerEngine,
        runner: ProcessRunner,
        output: Output,
    ) -> None:
        super().__init__(session_repo, translator, engine, runner, output)

    def create_window(self, name: str) -> Window:
        return DirectWindow(name)
