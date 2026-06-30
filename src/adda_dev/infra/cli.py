"""
adda-dev CLI entry point and composition root.
"""

import typer

from ..app.run import run_session
from ..common import AddaDevError
from .config import load_app_config
from .keyring_source import KeyringSecretSource
from .llm import resolve_backend
from .output import RichOutput
from .project import load_project

app = typer.Typer(no_args_is_help=True)


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
        project = load_project(project_name, config.project_defaults, source)
        backend = resolve_backend(project.backend, config.llm, source)
        run_session(project, backend, output)
    except AddaDevError as exc:
        output.error(exc)
        raise typer.Exit(1)
