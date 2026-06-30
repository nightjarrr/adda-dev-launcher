"""Tests for adda_dev.app.run."""

import pytest

from adda_dev.app.run import run_session
from adda_dev.domain.credentials import SecretError, SecretSource
from adda_dev.domain.github import GitHub
from adda_dev.domain.llm import AnthropicBackend, LlmBackend
from adda_dev.domain.project import Project
from adda_dev.domain.tmpfs import TmpfsSizes
from tests.conftest import FakeSecretSource


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


def _make_project(source: SecretSource) -> Project:
    gh = GitHub(owner="nightjarrr", repo="adda-dev-launcher", secret_name="demo-token", source=source)
    return Project(
        name="demo",
        github=gh,
        image="ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0",
        backend=LlmBackend.anthropic,
        tmpfs=TmpfsSizes(),
    )


def _make_backend(source: SecretSource) -> AnthropicBackend:
    return AnthropicBackend(secret_name="oauth", source=source)


# ---------------------------------------------------------------------------
# run_session — happy path
# ---------------------------------------------------------------------------


def test_run_session_info_called_with_secrets() -> None:
    fake = FakeSecretSource(
        {
            ("adda-dev:github", "demo-token"): "ghp_secret_token",
            ("adda-dev:anthropic", "oauth"): "claude_oauth_token",
        }
    )
    proj = _make_project(fake)
    backend = _make_backend(fake)
    output = FakeOutput()

    run_session(proj, backend, output)

    assert len(output.info_calls) >= 1
    assert any("ghp_" in msg for msg in output.info_calls)
    assert any("clau" in msg for msg in output.info_calls)


# ---------------------------------------------------------------------------
# run_session — SecretError propagates
# ---------------------------------------------------------------------------


def test_run_session_propagates_secret_error() -> None:
    empty_store = FakeSecretSource()
    proj = _make_project(empty_store)
    backend = _make_backend(empty_store)
    output = FakeOutput()

    with pytest.raises(SecretError):
        run_session(proj, backend, output)
