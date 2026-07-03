"""
Tests for adda_dev.infra.session: DirectWindow and DirectSessionManager.
"""

import pytest

from adda_dev.domain.contract import ContractSpec, ContractSpecDraft
from adda_dev.domain.github import GitHub
from adda_dev.domain.llm import AnthropicBackend, LlmBackend
from adda_dev.domain.process import ProcessHandle
from adda_dev.domain.project import Project
from adda_dev.domain.session_manager import Window
from adda_dev.domain.tmpfs import TmpfsSizes
from adda_dev.infra.session import DirectSessionManager, DirectWindow
from tests.conftest import FakeAddaPrimaryContainer, FakeOutput, FakeProxySidecar, FakeSecretSource, FakeSessionRepository


class _FakeProcessHandle(ProcessHandle):
    def wait(self) -> int:
        return 0

    def terminate(self) -> None:
        pass

    def stdout(self) -> str:
        return ""

    def stderr(self) -> str:
        return ""


class _FakeWindow(Window):
    """Window test double that records calls without running real processes."""

    def open(self, cmd: list[str], env: dict[str, str] | None = None) -> None:
        pass

    def attach(self) -> None:
        pass

    def close(self) -> None:
        pass


class _FakeWindowManager(DirectSessionManager):
    """DirectSessionManager that creates FakeWindows to avoid real subprocess execution."""

    def create_window(self, name: str) -> Window:
        return _FakeWindow(name)


def _make_draft(issue_id: int | None = None) -> ContractSpecDraft:
    source = FakeSecretSource(
        {
            ("adda-dev:github", "gh-token"): "ghp_test",
            ("adda-dev:anthropic", "claude-key"): "claude_test",
        }
    )
    gh = GitHub(owner="nightjarrr", repo="adda-dev-launcher", secret_name="gh-token", source=source)
    backend = AnthropicBackend(secret_name="claude-key", source=source)
    project = Project(
        name="test-project",
        github=gh,
        image="ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0",
        backend=LlmBackend.anthropic,
        tmpfs=TmpfsSizes(),
    )
    return ContractSpecDraft.initialize(project, backend, issue_id=issue_id)


def _make_manager(
    repo: FakeSessionRepository | None = None,
    sidecar: FakeProxySidecar | None = None,
    container: FakeAddaPrimaryContainer | None = None,
) -> _FakeWindowManager:
    repo = repo or FakeSessionRepository()
    sidecar = sidecar or FakeProxySidecar()
    container = container or FakeAddaPrimaryContainer()
    return _FakeWindowManager(
        repo,
        FakeOutput(),
        sidecar,
        container,
    )


# ---------------------------------------------------------------------------
# DirectWindow — open and attach
# ---------------------------------------------------------------------------


def test_directwindow_open_and_attach_returns_for_true() -> None:
    window = DirectWindow("test-window")
    window.open(["true"], {})
    window.attach()  # must return without blocking or raising


def test_directwindow_open_and_attach_returns_for_false() -> None:
    window = DirectWindow("test-window")
    window.open(["false"], {})
    window.attach()  # nonzero exit is ignored — attach must still return


def test_directwindow_open_and_attach_returns_for_echo() -> None:
    window = DirectWindow("test-window")
    window.open(["echo", "hello"], {})
    window.attach()


def test_directwindow_open_with_none_env() -> None:
    window = DirectWindow("test-window")
    window.open(["true"])  # env defaults to None
    window.attach()


# ---------------------------------------------------------------------------
# DirectWindow — close
# ---------------------------------------------------------------------------


def test_directwindow_close_is_noop() -> None:
    window = DirectWindow("test-window")
    window.open(["true"], {})
    window.attach()
    window.close()  # must not raise after attach has returned


def test_directwindow_close_without_open_is_noop() -> None:
    window = DirectWindow("test-window")
    window.close()  # must not raise even before open() is called


# ---------------------------------------------------------------------------
# DirectSessionManager — launch
# ---------------------------------------------------------------------------


def test_directsessionmanager_launch_calls_repo_create_with_project_name() -> None:
    repo = FakeSessionRepository()
    manager = _make_manager(repo)
    draft = _make_draft()
    manager._launch("my-project", draft)
    assert any(s.project_name == "my-project" for s in repo._sessions.values())


def test_directsessionmanager_launch_does_not_call_repo_delete() -> None:
    repo = FakeSessionRepository()
    manager = _make_manager(repo)
    manager._launch("my-project", _make_draft())
    assert len(repo.deleted) == 0


def test_directsessionmanager_launch_with_issue_id_creates_session() -> None:
    repo = FakeSessionRepository()
    manager = _make_manager(repo)
    manager._launch("my-project", _make_draft(issue_id=42))
    sessions = list(repo._sessions.values())
    assert sessions[0].issue_id == 42


def test_directsessionmanager_launch_starts_container() -> None:
    """_launch must call container.start with the created session and finalized spec."""
    repo = FakeSessionRepository()
    container = FakeAddaPrimaryContainer()
    manager = _make_manager(repo=repo, container=container)
    manager._launch("my-project", _make_draft())
    assert len(container.start_calls) == 1
    session, spec, _runner = container.start_calls[0]
    assert session.project_name == "my-project"
    assert isinstance(spec, ContractSpec)


# ---------------------------------------------------------------------------
# DirectSessionManager — terminate
# ---------------------------------------------------------------------------


def test_directsessionmanager_terminate_calls_repo_delete() -> None:
    repo = FakeSessionRepository()
    manager = _make_manager(repo)
    manager._launch("my-project", _make_draft())
    session_id = list(repo._sessions.keys())[0]
    manager._terminate()
    assert session_id in repo.deleted


def test_directsessionmanager_terminate_closes_windows() -> None:
    closed: list[str] = []

    class _TrackingWindow(_FakeWindow):
        def close(self) -> None:
            closed.append(self.name)

    class _TrackingManager(_FakeWindowManager):
        def create_window(self, name: str) -> _TrackingWindow:
            return _TrackingWindow(name)

    repo = FakeSessionRepository()
    manager = _TrackingManager(
        repo,
        FakeOutput(),
        FakeProxySidecar(),
        FakeAddaPrimaryContainer(),
    )
    manager._launch("my-project", _make_draft())
    manager._terminate()
    assert len(closed) == 1


def test_directsessionmanager_terminate_stops_sidecar() -> None:
    sidecar = FakeProxySidecar()
    manager = _make_manager(sidecar=sidecar)
    manager._launch("my-project", _make_draft())
    manager._terminate()
    assert sidecar.stop_calls == 1


def test_directsessionmanager_terminate_stops_container() -> None:
    """_terminate must call container.stop after closing windows."""
    container = FakeAddaPrimaryContainer()
    manager = _make_manager(container=container)
    manager._launch("my-project", _make_draft())
    manager._terminate()
    assert container.stop_calls == 1


def test_directsessionmanager_terminate_without_launch_is_safe() -> None:
    """terminate() must be None-safe when called before launch completes."""
    sidecar = FakeProxySidecar()
    manager = _make_manager(sidecar=sidecar)
    manager._terminate()  # _session is None; must not raise
    assert sidecar.stop_calls == 1


# ---------------------------------------------------------------------------
# SessionManager.run() — guaranteed teardown
# ---------------------------------------------------------------------------


class _FailingLaunchManager(_FakeWindowManager):
    """Manager whose _launch() always raises after creating a session."""

    def _launch(self, project_name: str, draft: ContractSpecDraft) -> None:
        # Create the session so _session is set, then raise to simulate partial failure
        self._repo.create(project_name, draft.issue_id)
        raise RuntimeError("simulated launch failure")


def test_sessionmanager_run_calls_terminate_even_when_launch_raises() -> None:
    sidecar = FakeProxySidecar()
    repo = FakeSessionRepository()
    manager = _FailingLaunchManager(
        repo,
        FakeOutput(),
        sidecar,
        FakeAddaPrimaryContainer(),
    )
    with pytest.raises(RuntimeError, match="simulated"):
        manager.run("my-project", _make_draft())
    # terminate() must have been called — sidecar.stop() is a proxy for that
    assert sidecar.stop_calls == 1
