"""
adda-dev CLI entry point and composition root.
"""

import signal
from types import FrameType

import typer

from ..app.run import RunOptions, run_session
from ..common import AddaDevError
from ..domain.llm import LlmProvider
from .adda_container import AddaPrimaryContainerImpl
from .config import load_app_config
from .container import create_engine
from .contract import DockerContractTranslator
from .keyring_source import KeyringSecretSource
from .llm import LlmConfigProviderRepository
from .output import RichOutput
from .project import TomlProjectRepository
from .proxy import EnvoySidecar
from .session import DirectSessionManager, FsSessionRepository


def _resolve_provider(provider: LlmProvider | None, anthropic: bool, deepseek: bool) -> LlmProvider | None:
    if anthropic and deepseek:
        raise typer.BadParameter("--anthropic and --deepseek are mutually exclusive")
    if provider is not None and (anthropic or deepseek):
        raise typer.BadParameter("--provider cannot be combined with --anthropic or --deepseek")
    if anthropic:
        return LlmProvider.anthropic
    if deepseek:
        return LlmProvider.deepseek
    return provider


def _terminate_on_sigterm(signum: int, frame: FrameType | None) -> None:
    """Convert SIGTERM to SystemExit so session teardown (finally blocks) runs before exit."""
    raise SystemExit(128 + signum)


app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """ADDA Dev Runtime launcher."""


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def run(
    ctx: typer.Context,
    project_name: str = typer.Argument(..., help="Project name from the registry"),
    issue_id: int | None = typer.Option(None, "--issue", help="GitHub issue number"),
    provider: LlmProvider | None = typer.Option(None, "--provider", help="LLM provider (overrides project file)"),
    anthropic: bool = typer.Option(False, "--anthropic", help="Shorthand for --provider anthropic"),
    deepseek: bool = typer.Option(False, "--deepseek", help="Shorthand for --provider deepseek"),
) -> None:
    """Start the ADDA Dev Runtime for a project. Pass `-- CMD...` to override the container command."""
    signal.signal(signal.SIGTERM, _terminate_on_sigterm)
    resolved = _resolve_provider(provider, anthropic, deepseek)
    cmd_override = tuple(ctx.args)
    source = KeyringSecretSource()
    output = RichOutput()

    try:
        config = load_app_config()
        output.ruler("adda-dev")
        engine = create_engine(config.container_engine, output)
        project_repo = TomlProjectRepository(config.project_defaults, source)
        provider_repo = LlmConfigProviderRepository(config.llm, source)
        sidecar = EnvoySidecar(engine, config.envoy_image, output)
        container = AddaPrimaryContainerImpl(engine, DockerContractTranslator(), output, cmd_override=cmd_override)
        session_manager = DirectSessionManager(FsSessionRepository(), output, sidecar, container)
        options = RunOptions(issue_id=issue_id, provider=resolved)
        run_session(project_name, project_repo, provider_repo, session_manager, output, options)
    except AddaDevError as exc:
        output.error(exc)
        raise typer.Exit(1)
