"""
run_session use case: retrieve credentials and display session info.
"""

from ..common import Output
from ..domain.llm import AnthropicBackend, DeepSeekBackend
from ..domain.project import Project


def run_session(project: Project, backend: AnthropicBackend | DeepSeekBackend, output: Output) -> None:
    """Retrieve credentials and display session info for the given project and backend."""
    output.info(str(project))
    output.info(str(backend))

    gh_secret = project.github.get_secret()
    backend_secret = backend.get_secret()

    output.info(f"GitHub token: {gh_secret[:4]}…")
    output.info(f"Backend token: {backend_secret[:4]}…")
