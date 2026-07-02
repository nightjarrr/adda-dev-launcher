"""
pytest configuration.
"""

from datetime import UTC, datetime
from pathlib import Path

from adda_dev.domain.container import ContainerEngine
from adda_dev.domain.contract import ContractSpec
from adda_dev.domain.credentials import SecretError, SecretSource
from adda_dev.domain.llm import AnthropicBackend, BackendRepository, DeepSeekBackend, LlmBackend
from adda_dev.domain.process import ProcessHandle, ProcessRunner
from adda_dev.domain.project import Project, ProjectNotFoundError, ProjectRepository
from adda_dev.domain.session import Session, SessionRepository
from adda_dev.domain.session_manager import SessionManager, Window


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
        self.deleted: list[str] = []
        self._counter = 0

    def create(self, project_name: str, issue_id: int | None = None) -> Session:
        self._counter += 1
        session_id = f"adda-dev-session-test-{self._counter:04d}"
        session = Session(
            session_id=session_id,
            project_name=project_name,
            started_at=datetime(2026, 1, 1, tzinfo=UTC),
            runtime_dir=Path(f"/tmp/fake-adda-dev/{session_id}"),
            issue_id=issue_id,
        )
        self._sessions[session_id] = session
        return session

    def delete(self, session: Session) -> None:
        self._sessions.pop(session.session_id, None)
        self.deleted.append(session.session_id)


class _FakeProcessHandle(ProcessHandle):
    """Minimal ProcessHandle whose wait() returns 0."""

    def wait(self) -> int:
        return 0

    def terminate(self) -> None:
        pass

    def stdout(self) -> str:
        return ""

    def stderr(self) -> str:
        return ""


class FakeContainerEngine(ContainerEngine):
    """ContainerEngine test double with canned properties; records calls and returns a trivial handle."""

    def __init__(self, rootless: bool = True, version: str = "27.0.0") -> None:
        self._rootless = rootless
        self._version = version
        self.calls: list[tuple[str, object]] = []

    @property
    def name(self) -> str:
        return "docker"

    @property
    def version(self) -> str:
        return self._version

    @property
    def rootless(self) -> bool:
        return self._rootless

    def pull(self, runner: ProcessRunner, image: str) -> ProcessHandle:
        self.calls.append(("pull", image))
        return _FakeProcessHandle()

    def run_it(
        self,
        runner: ProcessRunner,
        image: str,
        name: str,
        args: list[str],
        env: dict[str, str] | None = None,
        cmd: list[str] | None = None,
        remove: bool = False,
    ) -> ProcessHandle:
        self.calls.append(("run_it", (image, name, args, env, cmd, remove)))
        return _FakeProcessHandle()

    def run_d(
        self,
        runner: ProcessRunner,
        image: str,
        name: str,
        args: list[str],
        env: dict[str, str] | None = None,
        cmd: list[str] | None = None,
        remove: bool = False,
    ) -> ProcessHandle:
        self.calls.append(("run_d", (image, name, args, env, cmd, remove)))
        return _FakeProcessHandle()

    def stop(self, runner: ProcessRunner, name: str) -> ProcessHandle:
        self.calls.append(("stop", name))
        return _FakeProcessHandle()

    def exec(self, runner: ProcessRunner, name: str, cmd: list[str]) -> ProcessHandle:
        self.calls.append(("exec", (name, cmd)))
        return _FakeProcessHandle()

    def exec_it(self, runner: ProcessRunner, name: str, cmd: list[str]) -> ProcessHandle:
        self.calls.append(("exec_it", (name, cmd)))
        return _FakeProcessHandle()

    def logs_f(self, runner: ProcessRunner, name: str) -> ProcessHandle:
        self.calls.append(("logs_f", name))
        return _FakeProcessHandle()

    def inspect(self, runner: ProcessRunner, name: str) -> ProcessHandle:
        self.calls.append(("inspect", name))
        return _FakeProcessHandle()


class FakeSessionManager(SessionManager):
    """SessionManager test double that records launch and terminate calls without running real processes."""

    def __init__(self) -> None:
        self._fake_repo = FakeSessionRepository()
        super().__init__(self._fake_repo, _FakeContractTranslator(), FakeContainerEngine(), _FakeProcessRunner(), FakeOutput())
        self.launched: list[tuple[str, ContractSpec]] = []
        self.terminated: list[str] = []

    def create_window(self, name: str) -> Window:
        return _FakeWindow(name)

    def launch(self, project_name: str, spec: ContractSpec) -> Session:
        session = super().launch(project_name, spec)
        self.launched.append((project_name, spec))
        return session

    def terminate(self, session: Session) -> None:
        super().terminate(session)
        self.terminated.append(session.session_id)


class _FakeProcessRunner(ProcessRunner):
    """ProcessRunner test double that returns a trivial handle without launching a process."""

    def run(self, cmd: list[str], env: dict[str, str] | None = None) -> ProcessHandle:
        return _FakeProcessHandle()


class _FakeWindow(Window):
    """Window test double that records calls without running real processes."""

    def open(self, cmd: list[str], env: dict[str, str] | None = None) -> None:
        pass

    def attach(self) -> None:
        pass

    def close(self) -> None:
        pass


class _FakeContractTranslator:
    """ContractTranslator test double that returns a fixed no-op command."""

    def translate(self, spec: ContractSpec) -> object:
        from adda_dev.domain.contract import ContractProcessParams

        return ContractProcessParams(args=("true",), env={})
