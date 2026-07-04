"""
Launcher-container contract domain model: spec, translation output, translator port, and constants.
"""

import abc
from dataclasses import dataclass
from pathlib import Path

from ..common import AddaDevError
from .github import GitHub
from .llm import AnthropicProvider, DeepSeekProvider
from .project import Project
from .tmpfs import TmpfsSizes

# Fixed contract values — import these instead of repeating magic numbers.
CONTAINER_UID: int = 1000
CONTAINER_GID: int = 1000
CONTAINER_USERNAME: str = "adda"
PROXY_SOCKET: str = "/run/proxy.sock"
PROXY_PORT: int = 8080


class ContractError(AddaDevError):
    """Raised for contract-level failures such as timezone detection failure."""


@dataclass(frozen=True)
class ContractSpec:
    """Launcher obligations for a single container run, mapping 1:1 to §1 of the contract doc."""

    github: GitHub
    provider: AnthropicProvider | DeepSeekProvider
    image: str
    tmpfs: TmpfsSizes
    proxy_socket_host_path: Path
    proxy_socket: str = PROXY_SOCKET
    proxy_port: int = PROXY_PORT
    issue_id: int | None = None
    cap_drop_all: bool = True
    no_new_privileges: bool = True
    read_only: bool = True
    network_none: bool = True


@dataclass(frozen=True)
class ContractSpecDraft:
    """Incomplete contract spec holding all config-side fields; produced by initialize, completed by finalize."""

    github: GitHub
    provider: AnthropicProvider | DeepSeekProvider
    image: str
    tmpfs: TmpfsSizes
    proxy_socket: str = PROXY_SOCKET
    proxy_port: int = PROXY_PORT
    issue_id: int | None = None
    cap_drop_all: bool = True
    no_new_privileges: bool = True
    read_only: bool = True
    network_none: bool = True

    @classmethod
    def initialize(
        cls,
        project: Project,
        provider: AnthropicProvider | DeepSeekProvider,
        issue_id: int | None = None,
    ) -> ContractSpecDraft:
        """Seed a draft from a resolved project and its provider."""
        return cls(
            github=project.github,
            provider=provider,
            image=project.image,
            tmpfs=project.tmpfs,
            issue_id=issue_id,
        )

    def finalize(self, proxy_socket_host_path: Path) -> ContractSpec:
        """Bind the session-derived proxy socket path and return the complete spec."""
        return ContractSpec(
            github=self.github,
            provider=self.provider,
            image=self.image,
            tmpfs=self.tmpfs,
            proxy_socket_host_path=proxy_socket_host_path,
            proxy_socket=self.proxy_socket,
            proxy_port=self.proxy_port,
            issue_id=self.issue_id,
            cap_drop_all=self.cap_drop_all,
            no_new_privileges=self.no_new_privileges,
            read_only=self.read_only,
            network_none=self.network_none,
        )


@dataclass(frozen=True)
class ContractProcessParams:
    """Output of contract translation: CLI args (secrets by name only) and subprocess env (secret values)."""

    args: tuple[str, ...]
    env: dict[str, str]


class ContractTranslator(abc.ABC):
    """Port for translating a ContractSpec into engine-specific process parameters."""

    @abc.abstractmethod
    def translate(self, spec: ContractSpec) -> ContractProcessParams: ...
