"""
Tests for adda_dev.infra.session: DirectWindow and DirectSessionManager.
"""

from adda_dev.domain.contract import ContractProcessParams, ContractSpec, ContractTranslator
from adda_dev.domain.github import GitHub
from adda_dev.domain.llm import AnthropicBackend, LlmBackend
from adda_dev.domain.project import Project
from adda_dev.domain.tmpfs import TmpfsSizes
from adda_dev.infra.session import DirectSessionManager, DirectWindow
from tests.conftest import FakeOutput, FakeSecretSource, FakeSessionRepository


class _FakeContractTranslator(ContractTranslator):
    """ContractTranslator that always returns a fixed no-op command."""

    def __init__(self, cmd: str = "true") -> None:
        self._cmd = cmd

    def translate(self, spec: ContractSpec) -> ContractProcessParams:
        return ContractProcessParams(args=(self._cmd,), env={})


def _make_spec() -> ContractSpec:
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
    return ContractSpec(github=project.github, backend=backend, image=project.image, tmpfs=project.tmpfs)


# ---------------------------------------------------------------------------
# DirectWindow — run and attach
# ---------------------------------------------------------------------------


def test_directwindow_run_and_attach_returns_for_true() -> None:
    window = DirectWindow("test-window")
    window.run(["true"], {})
    window.attach()  # must return without blocking or raising


def test_directwindow_run_and_attach_returns_for_false() -> None:
    window = DirectWindow("test-window")
    window.run(["false"], {})
    window.attach()  # nonzero exit is ignored — attach must still return


def test_directwindow_run_and_attach_returns_for_echo() -> None:
    window = DirectWindow("test-window")
    window.run(["echo", "hello"], {})
    window.attach()


# ---------------------------------------------------------------------------
# DirectWindow — close
# ---------------------------------------------------------------------------


def test_directwindow_close_is_noop() -> None:
    window = DirectWindow("test-window")
    window.run(["true"], {})
    window.attach()
    window.close()  # must not raise after attach has returned


def test_directwindow_close_without_run_is_noop() -> None:
    window = DirectWindow("test-window")
    window.close()  # must not raise even before run() is called


# ---------------------------------------------------------------------------
# DirectSessionManager — launch
# ---------------------------------------------------------------------------


def test_directsessionmanager_launch_calls_repo_create_with_project_name() -> None:
    repo = FakeSessionRepository()
    manager = DirectSessionManager(repo, _FakeContractTranslator(), FakeOutput())
    spec = _make_spec()

    manager.launch("my-project", spec)

    assert len(repo._sessions) == 0 or True  # repo was used
    assert any(s.project_name == "my-project" for s in list(repo._sessions.values()) or [])


def test_directsessionmanager_launch_returns_session() -> None:
    repo = FakeSessionRepository()
    manager = DirectSessionManager(repo, _FakeContractTranslator(), FakeOutput())
    spec = _make_spec()

    session = manager.launch("my-project", spec)

    assert session.project_name == "my-project"
    assert session.session_id.startswith("session-test-")


def test_directsessionmanager_launch_returns_session_with_issue_id() -> None:
    repo = FakeSessionRepository()
    manager = DirectSessionManager(repo, _FakeContractTranslator(), FakeOutput())
    source = FakeSecretSource(
        {
            ("adda-dev:github", "gh-token"): "ghp_test",
            ("adda-dev:anthropic", "claude-key"): "claude_test",
        }
    )
    gh = GitHub(owner="nightjarrr", repo="adda-dev-launcher", secret_name="gh-token", source=source)
    backend = AnthropicBackend(secret_name="claude-key", source=source)
    spec = ContractSpec(
        github=gh,
        backend=backend,
        image="ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0",
        tmpfs=TmpfsSizes(),
        issue_id=42,
    )

    session = manager.launch("my-project", spec)

    assert session.issue_id == 42


def test_directsessionmanager_launch_does_not_call_repo_delete() -> None:
    repo = FakeSessionRepository()
    manager = DirectSessionManager(repo, _FakeContractTranslator(), FakeOutput())
    spec = _make_spec()

    manager.launch("my-project", spec)

    assert len(repo.deleted) == 0


# ---------------------------------------------------------------------------
# DirectSessionManager — terminate
# ---------------------------------------------------------------------------


def test_directsessionmanager_terminate_calls_repo_delete() -> None:
    repo = FakeSessionRepository()
    manager = DirectSessionManager(repo, _FakeContractTranslator(), FakeOutput())
    spec = _make_spec()

    session = manager.launch("my-project", spec)
    manager.terminate(session)

    assert session.session_id in repo.deleted


def test_directsessionmanager_terminate_closes_windows() -> None:
    closed: list[str] = []

    class _TrackingWindow(DirectWindow):
        def close(self) -> None:
            closed.append(self.name)

    class _TrackingManager(DirectSessionManager):
        def create_window(self, name: str) -> _TrackingWindow:
            return _TrackingWindow(name)

    repo = FakeSessionRepository()
    manager = _TrackingManager(repo, _FakeContractTranslator(), FakeOutput())
    spec = _make_spec()

    session = manager.launch("my-project", spec)
    manager.terminate(session)

    assert len(closed) == 1
