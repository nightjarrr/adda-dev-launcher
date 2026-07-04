"""
run_session use case: start a session and run the primary process.
"""

from dataclasses import dataclass

from ..common import Output
from ..domain.contract import ContractSpecDraft
from ..domain.llm import BackendRepository, LlmBackend
from ..domain.project import ProjectRepository
from ..domain.session_manager import SessionManager


@dataclass(frozen=True)
class RunOptions:
    issue_id: int | None = None
    provider: LlmBackend | None = None


def run_session(
    project_name: str,
    project_repo: ProjectRepository,
    backend_repo: BackendRepository,
    session_manager: SessionManager,
    output: Output,
    options: RunOptions = RunOptions(),
) -> None:
    """Retrieve project and backend config, launch a session, and block until the primary process exits."""
    project = project_repo.get(project_name)
    resolved_provider = options.provider or project.backend
    backend = backend_repo.get(resolved_provider)
    output.info(f"Project:  {project.name}")
    output.info(f"Image:    {project.image}")
    output.info(f"Backend:  {resolved_provider.value}")
    draft = ContractSpecDraft.initialize(project, backend, options.issue_id)
    session_manager.run(project_name, draft)
