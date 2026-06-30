"""
pytest configuration.
"""

from datetime import UTC, datetime
from pathlib import Path

from adda_dev.domain.credentials import SecretError, SecretSource
from adda_dev.domain.llm import AnthropicBackend, BackendRepository, DeepSeekBackend, LlmBackend
from adda_dev.domain.project import Project, ProjectNotFoundError, ProjectRepository
from adda_dev.domain.session import Session, SessionRepository


class FakeSecretSource(SecretSource):
    """SecretSource test double backed by a dict."""

    def __init__(self, secrets: dict[tuple[str, str], str] | None = None) -> None:
        self._secrets: dict[tuple[str, str], str] = secrets or {}

    def get(self, service: str, key: str) -> str:
        value = self._secrets.get((service, key))
        if value is None:
            raise SecretError(f"No secret for {service!r}/{key!r}")
        return value


class FakeOutput:
    """Output test double that captures calls."""

    def __init__(self) -> None:
        self.info_calls: list[str] = []
        self.warning_calls: list[str] = []
        self.error_calls: list[Exception] = []

    def info(self, message: str) -> None:
        self.info_calls.append(message)

    def warning(self, message: str) -> None:
        self.warning_calls.append(message)

    def error(self, exc: Exception) -> None:
        self.error_calls.append(exc)


class FakeProjectRepository(ProjectRepository):
    """ProjectRepository test double backed by a dict."""

    def __init__(self, projects: dict[str, Project]) -> None:
        self._projects = projects

    def get(self, name: str) -> Project:
        if name not in self._projects:
            raise ProjectNotFoundError(f"Project {name!r} not found")
        return self._projects[name]


class FakeBackendRepository(BackendRepository):
    """BackendRepository test double backed by a dict."""

    def __init__(self, backends: dict[LlmBackend, AnthropicBackend | DeepSeekBackend]) -> None:
        self._backends = backends

    def get(self, backend: LlmBackend) -> AnthropicBackend | DeepSeekBackend:
        return self._backends[backend]


class FakeSessionRepository(SessionRepository):
    """SessionRepository test double with deterministic IDs and in-memory state."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self.terminated: list[str] = []
        self._counter = 0

    def create(self, project_name: str, issue_id: int | None = None) -> Session:
        self._counter += 1
        session_id = f"session-test-{self._counter:04d}"
        session = Session(
            session_id=session_id,
            project_name=project_name,
            started_at=datetime(2026, 1, 1, tzinfo=UTC),
            runtime_dir=Path(f"/tmp/fake-adda-dev/{session_id}"),
            issue_id=issue_id,
        )
        self._sessions[session_id] = session
        return session

    def terminate(self, session: Session) -> None:
        self._sessions.pop(session.session_id, None)
        self.terminated.append(session.session_id)
