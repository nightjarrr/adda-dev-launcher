"""
adda-dev CLI entry point and composition root.
"""

import typer

from ..app.run import run_session
from ..common import AddaDevError
from ..domain.container import ContainerEngine
from .config import ContainerEngineChoice, load_app_config
from .container import DockerEngine
from .contract import DockerContractTranslator
from .keyring_source import KeyringSecretSource
from .llm import LlmConfigBackendRepository
from .output import RichOutput
from .process import CapturedOutputRunner, DefaultRunner
from .project import TomlProjectRepository
from .proxy import EnvoySidecar
from .session import DirectSessionManager, FsSessionRepository

app = typer.Typer(no_args_is_help=True)


def _make_engine(choice: ContainerEngineChoice) -> ContainerEngine:
    if choice is ContainerEngineChoice.docker:
        return DockerEngine()
    raise AddaDevError(f"Container engine '{choice.value}' is not supported yet; only 'docker' is available.")


@app.callback()
def main() -> None:
    """ADDA Dev Runtime launcher."""


@app.command()
def run(
    project_name: str = typer.Argument(..., help="Project name from the registry"),
    issue_id: int | None = typer.Option(None, "--issue", help="GitHub issue number"),
) -> None:
    """Start the ADDA Dev Runtime for a configured project."""
    source = KeyringSecretSource()
    output = RichOutput()

    try:
        config = load_app_config()
        engine = _make_engine(config.container_engine)
        project_repo = TomlProjectRepository(config.project_defaults, source)
        backend_repo = LlmConfigBackendRepository(config.llm, source)
        sidecar = EnvoySidecar(engine, CapturedOutputRunner(), config.envoy_image, output)
        session_manager = DirectSessionManager(
            FsSessionRepository(), DockerContractTranslator(), engine, DefaultRunner(), output, sidecar
        )
        run_session(project_name, project_repo, backend_repo, engine, session_manager, output, issue_id)
    except AddaDevError as exc:
        output.error(exc)
        raise typer.Exit(1)
