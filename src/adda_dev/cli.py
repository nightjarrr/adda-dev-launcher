"""
adda-dev CLI entry point.
"""

import rich
import typer

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
    from . import llm
    from .app_config import AppConfig
    from .credentials import SecretError
    from .project import Project, ProjectNotFoundError
    from .store import SchemaValidationError, TomlParseError

    try:
        config = AppConfig.load()
        project = Project.load(project_name, config.project_defaults)
        backend = llm.resolve_backend(project.backend, config.llm)
    except (ProjectNotFoundError, SchemaValidationError, TomlParseError) as exc:
        rich.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    rich.print(project)
    rich.print(backend)

    try:
        gh_secret = project.github.get_secret()
        backend_secret = backend.get_secret()
    except SecretError as exc:
        rich.print(f"[red]Secret error:[/red] {exc}")
        raise typer.Exit(1)

    rich.print(f"GitHub token: {gh_secret[:4]}…")
    rich.print(f"Backend token: {backend_secret[:4]}…")
