"""
run_session use case: start a session and run the primary process.
"""

from ..common import Output
from ..domain.contract import ContractSpec
from ..domain.llm import BackendRepository
from ..domain.project import ProjectRepository
from ..domain.session_manager import SessionManager


def run_session(
    project_name: str,
    project_repo: ProjectRepository,
    backend_repo: BackendRepository,
    session_manager: SessionManager,
    output: Output,
    issue_id: int | None = None,
) -> None:
    """Retrieve project and backend config, launch a session, and block until the primary process exits."""
    project = project_repo.get(project_name)
    backend = backend_repo.get(project.backend)
    output.info(f"Project:  {project.name}")
    output.info(f"Image:    {project.image}")
    output.info(f"Backend:  {project.backend.value}")
    spec = ContractSpec(
        github=project.github,
        backend=backend,
        image=project.image,
        tmpfs=project.tmpfs,
        issue_id=issue_id,
    )
    session = session_manager.launch(project_name, spec)
    session_manager.terminate(session)
