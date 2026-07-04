"""Tests for adda_dev.app.run."""

import pytest

from adda_dev.app.run import RunOptions, run_session
from adda_dev.domain.contract import ContractSpecDraft
from adda_dev.domain.github import GitHub
from adda_dev.domain.llm import AnthropicProvider, LlmProvider
from adda_dev.domain.project import Project
from adda_dev.domain.tmpfs import TmpfsSizes
from tests.conftest import (
    FakeOutput,
    FakeProjectRepository,
    FakeProviderRepository,
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
        provider=LlmProvider.anthropic,
        tmpfs=TmpfsSizes(),
    )


def _make_provider(source: FakeSecretSource) -> AnthropicProvider:
    return AnthropicProvider(secret_name="oauth", source=source)


# ---------------------------------------------------------------------------
# run_session — output
# ---------------------------------------------------------------------------


def test_run_session_output_includes_project_name() -> None:
    source = _make_fake_source()
    project = _make_project(source)
    provider = _make_provider(source)
    project_repo = FakeProjectRepository({"demo": project})
    provider_repo = FakeProviderRepository({LlmProvider.anthropic: provider})
    session_manager = FakeSessionManager()
    output = FakeOutput()

    run_session("demo", project_repo, provider_repo, session_manager, output, RunOptions())

    assert any("demo" in msg for msg in output.info_calls)


def test_run_session_output_includes_image() -> None:
    source = _make_fake_source()
    project = _make_project(source)
    provider = _make_provider(source)
    project_repo = FakeProjectRepository({"demo": project})
    provider_repo = FakeProviderRepository({LlmProvider.anthropic: provider})
    session_manager = FakeSessionManager()
    output = FakeOutput()

    run_session("demo", project_repo, provider_repo, session_manager, output, RunOptions())

    assert any("ghcr.io" in msg for msg in output.info_calls)


def test_run_session_output_includes_backend() -> None:
    source = _make_fake_source()
    project = _make_project(source)
    provider = _make_provider(source)
    project_repo = FakeProjectRepository({"demo": project})
    provider_repo = FakeProviderRepository({LlmProvider.anthropic: provider})
    session_manager = FakeSessionManager()
    output = FakeOutput()

    run_session("demo", project_repo, provider_repo, session_manager, output, RunOptions())

    assert any("anthropic" in msg for msg in output.info_calls)


# ---------------------------------------------------------------------------
# run_session — session lifecycle
# ---------------------------------------------------------------------------


def test_run_session_calls_run_with_draft() -> None:
    source = _make_fake_source()
    project = _make_project(source)
    provider = _make_provider(source)
    project_repo = FakeProjectRepository({"demo": project})
    provider_repo = FakeProviderRepository({LlmProvider.anthropic: provider})
    session_manager = FakeSessionManager()
    output = FakeOutput()

    run_session("demo", project_repo, provider_repo, session_manager, output, RunOptions())

    assert len(session_manager.launched) == 1
    assert session_manager.launched[0][0] == "demo"
    assert isinstance(session_manager.launched[0][1], ContractSpecDraft)


def test_run_session_calls_terminate_after_launch() -> None:
    source = _make_fake_source()
    project = _make_project(source)
    provider = _make_provider(source)
    project_repo = FakeProjectRepository({"demo": project})
    provider_repo = FakeProviderRepository({LlmProvider.anthropic: provider})
    session_manager = FakeSessionManager()
    output = FakeOutput()

    run_session("demo", project_repo, provider_repo, session_manager, output, RunOptions())

    assert session_manager.terminated == 1


def test_run_session_launch_passes_issue_id_in_draft() -> None:
    source = _make_fake_source()
    project = _make_project(source)
    provider = _make_provider(source)
    project_repo = FakeProjectRepository({"demo": project})
    provider_repo = FakeProviderRepository({LlmProvider.anthropic: provider})
    session_manager = FakeSessionManager()
    output = FakeOutput()

    run_session("demo", project_repo, provider_repo, session_manager, output, RunOptions(issue_id=42))

    assert session_manager.launched[0][1].issue_id == 42


# ---------------------------------------------------------------------------
# run_session — provider override
# ---------------------------------------------------------------------------


def test_run_session_provider_override_uses_specified_backend() -> None:
    from adda_dev.domain.llm import DeepSeekProvider

    source = _make_fake_source()
    project = _make_project(source)
    anthropic_provider = _make_provider(source)
    deepseek_provider = DeepSeekProvider(
        secret_name="deepseek-key",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        opus_model="deepseek-chat",
        sonnet_model="deepseek-chat",
        haiku_model="deepseek-chat",
        subagent_model="deepseek-chat",
        effort_level="high",
        source=source,
    )
    project_repo = FakeProjectRepository({"demo": project})
    provider_repo = FakeProviderRepository({LlmProvider.anthropic: anthropic_provider, LlmProvider.deepseek: deepseek_provider})
    session_manager = FakeSessionManager()
    output = FakeOutput()

    run_session("demo", project_repo, provider_repo, session_manager, output, RunOptions(provider=LlmProvider.deepseek))

    assert any("deepseek" in msg for msg in output.info_calls)


def test_run_session_provider_none_falls_back_to_project_backend() -> None:
    source = _make_fake_source()
    project = _make_project(source)
    provider = _make_provider(source)
    project_repo = FakeProjectRepository({"demo": project})
    provider_repo = FakeProviderRepository({LlmProvider.anthropic: provider})
    session_manager = FakeSessionManager()
    output = FakeOutput()

    run_session("demo", project_repo, provider_repo, session_manager, output, RunOptions(provider=None))

    assert any("anthropic" in msg for msg in output.info_calls)


# ---------------------------------------------------------------------------
# run_session — error propagation
# ---------------------------------------------------------------------------


def test_run_session_propagates_project_not_found() -> None:
    from adda_dev.domain.project import ProjectNotFoundError

    project_repo = FakeProjectRepository({})
    provider_repo = FakeProviderRepository({})
    session_manager = FakeSessionManager()
    output = FakeOutput()

    with pytest.raises(ProjectNotFoundError):
        run_session("missing", project_repo, provider_repo, session_manager, output)
