"""
run_session use case: start a session and run the primary process.
"""

from ..common import Output
from ..domain.container import ContainerEngine
from ..domain.contract import ContractSpecDraft
from ..domain.llm import BackendRepository
from ..domain.project import ProjectRepository
from ..domain.session_manager import SessionManager


def run_session(
    project_name: str,
    project_repo: ProjectRepository,
    backend_repo: BackendRepository,
    engine: ContainerEngine,
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
    output.info(f"Engine:   {engine.name} {engine.version} ({'rootless' if engine.rootless else 'root'})")
    if not engine.rootless:
        output.warning(
            "Running under root Docker; a container escape would hold host-root privileges — rootless Docker is recommended."
        )
    draft = ContractSpecDraft.from_project(project, backend, issue_id)
    session_manager.run(project_name, draft)
