"""
run_session use case: retrieve credentials and display session info.
"""

from ..common import Output
from ..domain.llm import BackendRepository
from ..domain.project import ProjectRepository
from ..domain.session import SessionRepository


def run_session(
    project_name: str,
    project_repo: ProjectRepository,
    backend_repo: BackendRepository,
    session_repo: SessionRepository,
    output: Output,
    issue_id: int | None = None,
) -> None:
    """Retrieve credentials and display session info for the given project and backend."""
    project = project_repo.get(project_name)
    backend = backend_repo.get(project.backend)
    session = session_repo.create(project_name, issue_id)
    try:
        output.info(f"Session:     {session.session_id}")
        output.info(f"Project:     {session.project_name}")
        output.info(f"Started:     {session.started_at.isoformat()}")
        output.info(f"Runtime dir: {session.runtime_dir}")
        if session.issue_id is not None:
            output.info(f"Issue:       #{session.issue_id}")
        output.info(f"Image:       {project.image}")
        output.info(f"Backend:     {project.backend.value}")

        gh_secret = project.github.get_secret()
        backend_secret = backend.get_secret()

        output.info(f"GitHub token: {gh_secret[:4]}…")
        output.info(f"Backend token: {backend_secret[:4]}…")
    finally:
        session_repo.terminate(session)
