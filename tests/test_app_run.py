"""Tests for adda_dev.app.run."""

import pytest

from adda_dev.app.run import run_session
from adda_dev.domain.credentials import SecretError
from adda_dev.domain.github import GitHub
from adda_dev.domain.llm import AnthropicBackend, LlmBackend
from adda_dev.domain.project import Project
from adda_dev.domain.tmpfs import TmpfsSizes
from tests.conftest import FakeBackendRepository, FakeOutput, FakeProjectRepository, FakeSecretSource


def _make_fake_source_with_secrets() -> FakeSecretSource:
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
# run_session — happy path
# ---------------------------------------------------------------------------


def test_run_session_info_called_with_secrets() -> None:
    fake = _make_fake_source_with_secrets()
    project = _make_project(fake)
    backend = _make_backend(fake)
    project_repo = FakeProjectRepository({"demo": project})
    backend_repo = FakeBackendRepository({LlmBackend.anthropic: backend})
    output = FakeOutput()

    run_session("demo", project_repo, backend_repo, output)

    assert len(output.info_calls) >= 1
    assert any("ghp_" in msg for msg in output.info_calls)
    assert any("clau" in msg for msg in output.info_calls)


# ---------------------------------------------------------------------------
# run_session — SecretError propagates
# ---------------------------------------------------------------------------


def test_run_session_propagates_secret_error() -> None:
    empty_store = FakeSecretSource()
    project = _make_project(empty_store)
    backend = _make_backend(empty_store)
    project_repo = FakeProjectRepository({"demo": project})
    backend_repo = FakeBackendRepository({LlmBackend.anthropic: backend})
    output = FakeOutput()

    with pytest.raises(SecretError):
        run_session("demo", project_repo, backend_repo, output)


# ---------------------------------------------------------------------------
# run_session — project not found propagates
# ---------------------------------------------------------------------------


def test_run_session_propagates_project_not_found() -> None:
    from adda_dev.domain.project import ProjectNotFoundError

    project_repo = FakeProjectRepository({})
    backend_repo = FakeBackendRepository({})
    output = FakeOutput()

    with pytest.raises(ProjectNotFoundError):
        run_session("missing", project_repo, backend_repo, output)
