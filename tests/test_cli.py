"""Tests for adda_dev.infra.cli."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from adda_dev.domain.container import ContainerEngineUnavailableError
from adda_dev.domain.credentials import SecretSource
from adda_dev.domain.github import GitHub
from adda_dev.domain.llm import AnthropicBackend, LlmBackend
from adda_dev.domain.project import Project
from adda_dev.domain.tmpfs import TmpfsSizes
from adda_dev.infra.cli import app
from adda_dev.infra.config import ContainerEngineChoice
from adda_dev.infra.llm import LlmConfig
from tests.conftest import FakeContainerEngine, FakeSecretSource

runner = CliRunner()


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


def _make_mock_config(engine_choice: ContainerEngineChoice = ContainerEngineChoice.docker) -> MagicMock:
    mock_config = MagicMock()
    mock_config.project_defaults = MagicMock()
    mock_config.llm = LlmConfig()
    mock_config.container_engine = engine_choice
    return mock_config


# ---------------------------------------------------------------------------
# run — happy path: project/image/backend info printed, exit 0
# ---------------------------------------------------------------------------


def test_run_displays_project_info_and_exits_0() -> None:
    fake = FakeSecretSource(
        {
            ("adda-dev:github", "demo-token"): "ghp_secret_token",
            ("adda-dev:anthropic", "oauth"): "claude_oauth_token",
        }
    )
    proj = _make_project(fake)
    backend = _make_backend(fake)

    mock_config = _make_mock_config()
    mock_project_repo = MagicMock()
    mock_project_repo.get.return_value = proj
    mock_backend_repo = MagicMock()
    mock_backend_repo.get.return_value = backend
    mock_session_manager = MagicMock()
    mock_session_manager.launch.return_value = MagicMock(session_id="adda-dev-session-test0001")
    fake_engine = FakeContainerEngine()

    with (
        patch("adda_dev.infra.cli.load_app_config", return_value=mock_config),
        patch("adda_dev.infra.cli.DockerEngine", return_value=fake_engine),
        patch("adda_dev.infra.cli.TomlProjectRepository", return_value=mock_project_repo),
        patch("adda_dev.infra.cli.LlmConfigBackendRepository", return_value=mock_backend_repo),
        patch("adda_dev.infra.cli.DirectSessionManager", return_value=mock_session_manager),
    ):
        result = runner.invoke(app, ["run", "demo"])

    assert result.exit_code == 0


def test_run_no_project_name_exits_nonzero() -> None:
    result = runner.invoke(app, ["run"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# run — project not found → exit 1
# ---------------------------------------------------------------------------


def test_run_project_not_found_exits_1() -> None:
    from adda_dev.domain.project import ProjectNotFoundError

    mock_config = _make_mock_config()
    mock_project_repo = MagicMock()
    mock_project_repo.get.side_effect = ProjectNotFoundError("not found")
    fake_engine = FakeContainerEngine()

    with (
        patch("adda_dev.infra.cli.load_app_config", return_value=mock_config),
        patch("adda_dev.infra.cli.DockerEngine", return_value=fake_engine),
        patch("adda_dev.infra.cli.TomlProjectRepository", return_value=mock_project_repo),
        patch("adda_dev.infra.cli.LlmConfigBackendRepository", return_value=MagicMock()),
        patch("adda_dev.infra.cli.DirectSessionManager", return_value=MagicMock()),
    ):
        result = runner.invoke(app, ["run", "nonexistent"])

    assert result.exit_code == 1
    assert "Error" in result.output


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

    mock_config = _make_mock_config()
    mock_project_repo = MagicMock()
    mock_project_repo.get.return_value = proj
    mock_backend_repo = MagicMock()
    mock_backend_repo.get.return_value = backend
    mock_session_manager = MagicMock()
    mock_session_manager.launch.return_value = MagicMock(session_id="adda-dev-session-test0001")
    fake_engine = FakeContainerEngine()

    with (
        patch("adda_dev.infra.cli.load_app_config", return_value=mock_config),
        patch("adda_dev.infra.cli.DockerEngine", return_value=fake_engine),
        patch("adda_dev.infra.cli.TomlProjectRepository", return_value=mock_project_repo),
        patch("adda_dev.infra.cli.LlmConfigBackendRepository", return_value=mock_backend_repo),
        patch("adda_dev.infra.cli.DirectSessionManager", return_value=mock_session_manager),
    ):
        result = runner.invoke(app, ["run", "demo", "--issue", "42"])

    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# run — podman engine choice → exit 1 with "not supported" message
# ---------------------------------------------------------------------------


def test_run_podman_engine_exits_1_with_not_supported() -> None:
    mock_config = _make_mock_config(ContainerEngineChoice.podman)

    with patch("adda_dev.infra.cli.load_app_config", return_value=mock_config):
        result = runner.invoke(app, ["run", "demo"])

    assert result.exit_code == 1
    assert "not supported" in result.output


# ---------------------------------------------------------------------------
# run — DockerEngine raises ContainerEngineUnavailableError → exit 1
# ---------------------------------------------------------------------------


def test_run_docker_engine_unavailable_exits_1() -> None:
    mock_config = _make_mock_config()

    with (
        patch("adda_dev.infra.cli.load_app_config", return_value=mock_config),
        patch("adda_dev.infra.cli.DockerEngine", side_effect=ContainerEngineUnavailableError("Docker not found")),
    ):
        result = runner.invoke(app, ["run", "demo"])

    assert result.exit_code == 1
    assert "Error" in result.output
