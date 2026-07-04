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
    output.kv("Project", project.name)
    output.kv("Provider", str(resolved_provider))
    output.kv("Container", project.image)
    output.kv("GitHub", f"{project.github.owner}/{project.github.repo}")
    output.kv(
        "Tmpfs",
        (
            f"home {project.tmpfs.home}",
            f"workspace {project.tmpfs.workspace}",
            f"tmp {project.tmpfs.tmp}",
        ),
    )
    draft = ContractSpecDraft.initialize(project, provider, options.issue_id)
    session_manager.run(project_name, draft)
