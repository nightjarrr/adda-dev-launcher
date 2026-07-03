"""
adda-dev CLI entry point and composition root.
"""

import signal
from types import FrameType

import typer

from ..app.run import run_session
from ..common import AddaDevError
from .adda_container import AddaPrimaryContainerImpl
from .config import load_app_config
from .container import create_engine
from .contract import DockerContractTranslator
from .keyring_source import KeyringSecretSource
from .llm import LlmConfigBackendRepository
from .output import RichOutput
from .project import TomlProjectRepository
from .proxy import EnvoySidecar
from .session import DirectSessionManager, FsSessionRepository


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
) -> None:
    """Start the ADDA Dev Runtime for a project. Pass `-- CMD...` to override the container command."""
    signal.signal(signal.SIGTERM, _terminate_on_sigterm)
    cmd_override = tuple(ctx.args)
    source = KeyringSecretSource()
    output = RichOutput()

    try:
        config = load_app_config()
        engine = create_engine(config.container_engine, output)
        project_repo = TomlProjectRepository(config.project_defaults, source)
        backend_repo = LlmConfigBackendRepository(config.llm, source)
        sidecar = EnvoySidecar(engine, config.envoy_image, output)
        container = AddaPrimaryContainerImpl(engine, DockerContractTranslator(), cmd_override=cmd_override)
        session_manager = DirectSessionManager(FsSessionRepository(), output, sidecar, container)
        run_session(project_name, project_repo, backend_repo, session_manager, output, issue_id)
    except AddaDevError as exc:
        output.error(exc)
        raise typer.Exit(1)
