"""
run_session use case: start a session and run the primary process.
"""

from dataclasses import dataclass

from ..common import Output
from ..domain.contract import ContractSpecDraft
from ..domain.llm import LlmProvider, ProviderRepository
from ..domain.project import ProjectRepository
from ..domain.session_manager import SessionManager


@dataclass(frozen=True)
class RunOptions:
    issue_id: int | None = None
    provider: LlmProvider | None = None


def run_session(
    project_name: str,
    project_repo: ProjectRepository,
    provider_repo: ProviderRepository,
    session_manager: SessionManager,
    output: Output,
    options: RunOptions = RunOptions(),
) -> None:
    """Retrieve project and provider config, launch a session, and block until the primary process exits."""
    project = project_repo.get(project_name)
    resolved_provider = options.provider or project.provider
    provider = provider_repo.get(resolved_provider)
    output.info(f"Project:  {project.name}")
    output.info(f"Image:    {project.image}")
    output.info(f"Provider: {resolved_provider.value}")
    draft = ContractSpecDraft.initialize(project, provider, options.issue_id)
    session_manager.run(project_name, draft)
