"""Tests for adda_dev.infra.cli."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from adda_dev.domain.credentials import SecretSource
from adda_dev.domain.github import GitHub
from adda_dev.domain.llm import AnthropicBackend, LlmBackend
from adda_dev.domain.project import Project
from adda_dev.domain.tmpfs import TmpfsSizes
from adda_dev.infra.cli import app
from adda_dev.infra.llm import LlmConfig
from tests.conftest import FakeSecretSource

runner = CliRunner()

DATA_DIR = Path(__file__).parent / "data" / "config"


# ---------------------------------------------------------------------------
# Fixtures: a pre-built Project and backend with FakeSecretSource injected
# ---------------------------------------------------------------------------


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
# run — happy path: abbreviated tokens printed, exit 0
# ---------------------------------------------------------------------------


def test_run_prints_abbreviated_secrets_and_exits_0() -> None:
    fake = FakeSecretSource(
        {
            ("adda-dev:github", "demo-token"): "ghp_secret_token",
            ("adda-dev:anthropic", "oauth"): "claude_oauth_token",
        }
    )
    proj = _make_project(fake)
    backend = _make_backend(fake)

    mock_config = MagicMock()
    mock_config.project_defaults = MagicMock()
    mock_config.llm = LlmConfig()

    with (
        patch("adda_dev.infra.cli.load_app_config", return_value=mock_config),
        patch("adda_dev.infra.cli.load_project", return_value=proj),
        patch("adda_dev.infra.cli.resolve_backend", return_value=backend),
    ):
        result = runner.invoke(app, ["run", "demo"])

    assert result.exit_code == 0
    assert "ghp_" in result.output
    assert "clau" in result.output


def test_run_no_project_name_exits_nonzero() -> None:
    result = runner.invoke(app, ["run"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# run — project not found → exit 1
# ---------------------------------------------------------------------------


def test_run_project_not_found_exits_1() -> None:
    from adda_dev.domain.project import ProjectNotFoundError

    mock_config = MagicMock()
    mock_config.project_defaults = MagicMock()

    with (
        patch("adda_dev.infra.cli.load_app_config", return_value=mock_config),
        patch("adda_dev.infra.cli.load_project", side_effect=ProjectNotFoundError("not found")),
    ):
        result = runner.invoke(app, ["run", "nonexistent"])

    assert result.exit_code == 1
    assert "Error" in result.output


# ---------------------------------------------------------------------------
# run — secret error → exit 1
# ---------------------------------------------------------------------------


def test_run_secret_error_exits_1() -> None:
    empty_store = FakeSecretSource()
    proj = _make_project(empty_store)
    backend = _make_backend(empty_store)

    mock_config = MagicMock()
    mock_config.project_defaults = MagicMock()
    mock_config.llm = LlmConfig()

    with (
        patch("adda_dev.infra.cli.load_app_config", return_value=mock_config),
        patch("adda_dev.infra.cli.load_project", return_value=proj),
        patch("adda_dev.infra.cli.resolve_backend", return_value=backend),
    ):
        result = runner.invoke(app, ["run", "demo"])

    assert result.exit_code == 1
    assert "Secret error" in result.output


# ---------------------------------------------------------------------------
# run — issue option is accepted
# ---------------------------------------------------------------------------


def test_run_with_issue_option_exits_0() -> None:
    fake = FakeSecretSource(
        {
            ("adda-dev:github", "demo-token"): "ghp_secret_token",
            ("adda-dev:anthropic", "oauth"): "claude_oauth_token",
        }
    )
    proj = _make_project(fake)
    backend = _make_backend(fake)

    mock_config = MagicMock()
    mock_config.project_defaults = MagicMock()
    mock_config.llm = LlmConfig()

    with (
        patch("adda_dev.infra.cli.load_app_config", return_value=mock_config),
        patch("adda_dev.infra.cli.load_project", return_value=proj),
        patch("adda_dev.infra.cli.resolve_backend", return_value=backend),
    ):
        result = runner.invoke(app, ["run", "demo", "--issue", "42"])

    assert result.exit_code == 0
