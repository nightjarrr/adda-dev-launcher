"""
run_session use case: retrieve credentials and display session info.
"""

from ..common import Output
from ..domain.llm import BackendRepository
from ..domain.project import ProjectRepository


def run_session(project_name: str, project_repo: ProjectRepository, backend_repo: BackendRepository, output: Output) -> None:
    """Retrieve credentials and display session info for the given project and backend."""
    project = project_repo.get(project_name)
    backend = backend_repo.get(project.backend)
    output.info(str(project))
    output.info(str(backend))

    gh_secret = project.github.get_secret()
    backend_secret = backend.get_secret()

    output.info(f"GitHub token: {gh_secret[:4]}…")
    output.info(f"Backend token: {backend_secret[:4]}…")
