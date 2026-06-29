"""
run_session use case: retrieve credentials and display session info.
"""

import rich
import typer

from ..domain.credentials import SecretError
from ..domain.llm import AnthropicBackend, DeepSeekBackend
from ..domain.project import Project


def run_session(project: Project, backend: AnthropicBackend | DeepSeekBackend) -> None:
    """Retrieve credentials and display session info for the given project and backend."""
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
