"""
pytest configuration.
"""

from datetime import UTC, datetime
from pathlib import Path

from adda_dev.domain.adda_container import AddaPrimaryContainer
from adda_dev.domain.contract import ContractSpec, ContractSpecDraft
from adda_dev.domain.credentials import SecretError, SecretSource
from adda_dev.domain.llm import AnthropicProvider, DeepSeekProvider, LlmProvider, ProviderRepository
from adda_dev.domain.project import Project, ProjectNotFoundError, ProjectRepository
from adda_dev.domain.proxy import ProxySidecar
from adda_dev.domain.session import Session, SessionRepository
from adda_dev.domain.session_manager import SessionManager
from adda_dev.domain.window import Window
from adda_dev.infra.container import ContainerEngine
from adda_dev.infra.process import ProcessHandle, ProcessRunner


class FakeSecretSource(SecretSource):
    """SecretSource test double backed by a dict."""

    def __init__(self, secrets: dict[tuple[str, str], str] | None = None) -> None:
        self._secrets: dict[tuple[str, str], str] = secrets or {}

    def get(self, service: str, key: str) -> str:
        value = self._secrets.get((service, key))
        if value is None:
            raise SecretError(f"No secret for {service!r}/{key!r}")
        return value


class FakeStepContext:
    """StepContext test double that records completion or failure."""

    def __init__(self, label: str, step_calls: list[tuple[str, str | None]]) -> None:
        self._label = label
        self._step_calls = step_calls

    def __enter__(self) -> FakeStepContext:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> bool:
        if exc_type is not None:
            self._step_calls.append((self._label, None))
        return False

    def done(self, detail: str) -> None:
        self._step_calls.append((self._label, detail))


class FakeOutput:
    """Output test double that captures calls."""

    def __init__(self) -> None:
        self.info_calls: list[str] = []
        self.warning_calls: list[str] = []
        self.error_calls: list[Exception] = []
        self.ruler_calls: list[str] = []
        self.blank_count: int = 0
        self.kv_calls: list[tuple[str, str | tuple[str, ...]]] = []
        self.step_calls: list[tuple[str, str | None]] = []

    def info(self, message: str) -> None:
        self.info_calls.append(message)

    def warning(self, message: str) -> None:
        self.warning_calls.append(message)

    def error(self, exc: Exception) -> None:
        self.error_calls.append(exc)

    def ruler(self, title: str = "", *, pad: bool = True) -> None:
        self.ruler_calls.append(title)
        if pad:
            self.blank_count += 2

    def blank(self) -> None:
        self.blank_count += 1

    def kv(self, key: str, value: str | tuple[str, ...]) -> None:
        self.kv_calls.append((key, value))

    def step(self, label: str) -> FakeStepContext:
        return FakeStepContext(label, self.step_calls)


class FakeProjectRepository(ProjectRepository):
    """ProjectRepository test double backed by a dict."""

    def __init__(self, projects: dict[str, Project]) -> None:
        self._projects = projects

    def get(self, name: str) -> Project:
        if name not in self._projects:
            raise ProjectNotFoundError(f"Project {name!r} not found")
        return self._projects[name]


class FakeProviderRepository(ProviderRepository):
    """ProviderRepository test double backed by a dict."""

    def __init__(self, providers: dict[LlmProvider, AnthropicProvider | DeepSeekProvider]) -> None:
        self._providers = providers

    def get(self, provider: LlmProvider) -> AnthropicProvider | DeepSeekProvider:
        return self._providers[provider]


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

    def __init__(self) -> None:
        super().__init__([])

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

    def rm(self, runner: ProcessRunner, name: str, force: bool = False) -> ProcessHandle:
        self.calls.append(("rm", (name, force)))
        return _FakeProcessHandle()

    def logs(self, runner: ProcessRunner, name: str) -> ProcessHandle:
        self.calls.append(("logs", name))
        return _FakeProcessHandle()


class FakeProxySidecar(ProxySidecar):
    """ProxySidecar test double that records calls and returns a canned host path."""

    def __init__(self, host_socket: Path | None = None) -> None:
        self._host_socket = host_socket or Path("/tmp/fake-proxy/proxy_socket/proxy.sock")
        self.start_calls: list[Session] = []
        self.stop_calls: int = 0

    def start(self, session: Session) -> Path:
        self.start_calls.append(session)
        return self._host_socket

    def stop(self) -> None:
        self.stop_calls += 1


class FakeAddaPrimaryContainer(AddaPrimaryContainer):
    """AddaPrimaryContainer test double that records start and stop calls."""

    def __init__(self) -> None:
        self.start_calls: list[tuple[Session, ContractSpec, Window]] = []
        self.stop_calls: int = 0

    def start(self, session: Session, spec: ContractSpec, window: Window) -> None:
        self.start_calls.append((session, spec, window))

    def stop(self) -> None:
        self.stop_calls += 1


class FakeSessionManager(SessionManager):
    """SessionManager test double that records launch and terminate calls without running real processes."""

    def __init__(self) -> None:
        self._fake_repo = FakeSessionRepository()
        super().__init__(
            self._fake_repo,
            FakeOutput(),
            FakeProxySidecar(),
            FakeAddaPrimaryContainer(),
        )
        self.launched: list[tuple[str, ContractSpecDraft]] = []
        self.terminated: int = 0

    def create_window(self, name: str) -> Window:
        return _FakeWindow(name)

    def _launch(self, project_name: str, draft: ContractSpecDraft) -> None:
        super()._launch(project_name, draft)
        self.launched.append((project_name, draft))

    def _terminate(self) -> None:
        super()._terminate()
        self.terminated += 1


class _FakeWindow(Window):
    """Window test double that records calls without running real processes."""

    def open(self, cmd: list[str], env: dict[str, str] | None = None) -> None:
        pass

    def attach(self) -> None:
        pass

    def close(self) -> None:
        pass
