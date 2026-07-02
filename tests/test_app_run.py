"""Tests for adda_dev.app.run."""

import pytest

from adda_dev.app.run import run_session
from adda_dev.domain.github import GitHub
from adda_dev.domain.llm import AnthropicBackend, LlmBackend
from adda_dev.domain.project import Project
from adda_dev.domain.tmpfs import TmpfsSizes
from tests.conftest import (
    FakeBackendRepository,
    FakeContainerEngine,
    FakeOutput,
    FakeProjectRepository,
    FakeSecretSource,
    FakeSessionManager,
)


def _make_fake_source() -> FakeSecretSource:
    return FakeSecretSource(
        {
            ("adda-dev:github", "demo-token"): "ghp_secret_token",
            ("adda-dev:anthropic", "oauth"): "claude_oauth_token",
        }
    )


def _make_project(source: FakeSecretSource) -> Project:
    gh = GitHub(owner="nightjarrr", repo="adda-dev-launcher", secret_name="demo-token", source=source)
    return Project(
        name="demo",
        github=gh,
        image="ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0",
        backend=LlmBackend.anthropic,
        tmpfs=TmpfsSizes(),
    )


def _make_backend(source: FakeSecretSource) -> AnthropicBackend:
    return AnthropicBackend(secret_name="oauth", source=source)


# ---------------------------------------------------------------------------
# run_session — output
# ---------------------------------------------------------------------------


def test_run_session_output_includes_project_name() -> None:
    source = _make_fake_source()
    project = _make_project(source)
    backend = _make_backend(source)
    project_repo = FakeProjectRepository({"demo": project})
    backend_repo = FakeBackendRepository({LlmBackend.anthropic: backend})
    session_manager = FakeSessionManager()
    engine = FakeContainerEngine()
    output = FakeOutput()

    run_session("demo", project_repo, backend_repo, engine, session_manager, output)

    assert any("demo" in msg for msg in output.info_calls)


def test_run_session_output_includes_image() -> None:
    source = _make_fake_source()
    project = _make_project(source)
    backend = _make_backend(source)
    project_repo = FakeProjectRepository({"demo": project})
    backend_repo = FakeBackendRepository({LlmBackend.anthropic: backend})
    session_manager = FakeSessionManager()
    engine = FakeContainerEngine()
    output = FakeOutput()

    run_session("demo", project_repo, backend_repo, engine, session_manager, output)

    assert any("ghcr.io" in msg for msg in output.info_calls)


def test_run_session_output_includes_backend() -> None:
    source = _make_fake_source()
    project = _make_project(source)
    backend = _make_backend(source)
    project_repo = FakeProjectRepository({"demo": project})
    backend_repo = FakeBackendRepository({LlmBackend.anthropic: backend})
    session_manager = FakeSessionManager()
    engine = FakeContainerEngine()
    output = FakeOutput()

    run_session("demo", project_repo, backend_repo, engine, session_manager, output)

    assert any("anthropic" in msg for msg in output.info_calls)


# ---------------------------------------------------------------------------
# run_session — Engine banner
# ---------------------------------------------------------------------------


def test_run_session_output_includes_engine_info() -> None:
    source = _make_fake_source()
    project = _make_project(source)
    backend = _make_backend(source)
    project_repo = FakeProjectRepository({"demo": project})
    backend_repo = FakeBackendRepository({LlmBackend.anthropic: backend})
    session_manager = FakeSessionManager()
    engine = FakeContainerEngine(rootless=True, version="27.1.1")
    output = FakeOutput()

    run_session("demo", project_repo, backend_repo, engine, session_manager, output)

    assert any("docker" in msg and "27.1.1" in msg and "rootless" in msg for msg in output.info_calls)


def test_run_session_rootless_engine_no_warning() -> None:
    source = _make_fake_source()
    project = _make_project(source)
    backend = _make_backend(source)
    project_repo = FakeProjectRepository({"demo": project})
    backend_repo = FakeBackendRepository({LlmBackend.anthropic: backend})
    session_manager = FakeSessionManager()
    engine = FakeContainerEngine(rootless=True)
    output = FakeOutput()

    run_session("demo", project_repo, backend_repo, engine, session_manager, output)

    assert len(output.warning_calls) == 0


def test_run_session_root_engine_emits_warning() -> None:
    source = _make_fake_source()
    project = _make_project(source)
    backend = _make_backend(source)
    project_repo = FakeProjectRepository({"demo": project})
    backend_repo = FakeBackendRepository({LlmBackend.anthropic: backend})
    session_manager = FakeSessionManager()
    engine = FakeContainerEngine(rootless=False)
    output = FakeOutput()

    run_session("demo", project_repo, backend_repo, engine, session_manager, output)

    assert len(output.warning_calls) == 1
    assert "root" in output.warning_calls[0].lower() or "rootless" in output.warning_calls[0].lower()


def test_run_session_output_includes_root_in_engine_banner_when_not_rootless() -> None:
    source = _make_fake_source()
    project = _make_project(source)
    backend = _make_backend(source)
    project_repo = FakeProjectRepository({"demo": project})
    backend_repo = FakeBackendRepository({LlmBackend.anthropic: backend})
    session_manager = FakeSessionManager()
    engine = FakeContainerEngine(rootless=False, version="27.1.1")
    output = FakeOutput()

    run_session("demo", project_repo, backend_repo, engine, session_manager, output)

    assert any("docker" in msg and "27.1.1" in msg and "root" in msg for msg in output.info_calls)


# ---------------------------------------------------------------------------
# run_session — session lifecycle
# ---------------------------------------------------------------------------


def test_run_session_calls_launch_with_correct_project_name() -> None:
    source = _make_fake_source()
    project = _make_project(source)
    backend = _make_backend(source)
    project_repo = FakeProjectRepository({"demo": project})
    backend_repo = FakeBackendRepository({LlmBackend.anthropic: backend})
    session_manager = FakeSessionManager()
    engine = FakeContainerEngine()
    output = FakeOutput()

    run_session("demo", project_repo, backend_repo, engine, session_manager, output)

    assert len(session_manager.launched) == 1
    assert session_manager.launched[0][0] == "demo"


def test_run_session_calls_terminate_after_launch() -> None:
    source = _make_fake_source()
    project = _make_project(source)
    backend = _make_backend(source)
    project_repo = FakeProjectRepository({"demo": project})
    backend_repo = FakeBackendRepository({LlmBackend.anthropic: backend})
    session_manager = FakeSessionManager()
    engine = FakeContainerEngine()
    output = FakeOutput()

    run_session("demo", project_repo, backend_repo, engine, session_manager, output)

    assert len(session_manager.terminated) == 1


def test_run_session_launch_passes_issue_id_in_spec() -> None:
    source = _make_fake_source()
    project = _make_project(source)
    backend = _make_backend(source)
    project_repo = FakeProjectRepository({"demo": project})
    backend_repo = FakeBackendRepository({LlmBackend.anthropic: backend})
    session_manager = FakeSessionManager()
    engine = FakeContainerEngine()
    output = FakeOutput()

    run_session("demo", project_repo, backend_repo, engine, session_manager, output, issue_id=42)

    assert session_manager.launched[0][1].issue_id == 42


# ---------------------------------------------------------------------------
# run_session — error propagation
# ---------------------------------------------------------------------------


def test_run_session_propagates_project_not_found() -> None:
    from adda_dev.domain.project import ProjectNotFoundError

    project_repo = FakeProjectRepository({})
    backend_repo = FakeBackendRepository({})
    session_manager = FakeSessionManager()
    engine = FakeContainerEngine()
    output = FakeOutput()

    with pytest.raises(ProjectNotFoundError):
        run_session("missing", project_repo, backend_repo, engine, session_manager, output)
