"""
Launcher-container contract domain model: spec, translation output, translator port, and constants.
"""

import abc
from dataclasses import dataclass

from ..common import AddaDevError
from .github import GitHub
from .llm import AnthropicBackend, DeepSeekBackend
from .tmpfs import TmpfsSizes

# Fixed contract values — import these instead of repeating magic numbers.
CONTAINER_UID: int = 1000
CONTAINER_GID: int = 1000
CONTAINER_USERNAME: str = "adda"
PROXY_SOCKET: str = "/run/proxy.sock"
PROXY_PORT: int = 8080
RUN_TMPFS_SIZE: str = "32m"
TMPFS_MODE: str = "700"


class ContractError(AddaDevError):
    """Raised for contract-level failures such as timezone detection failure."""


@dataclass(frozen=True)
class ContractSpec:
    """Launcher obligations for a single container run, mapping 1:1 to §1 of the contract doc."""

    github: GitHub
    backend: AnthropicBackend | DeepSeekBackend
    image: str
    tmpfs: TmpfsSizes
    proxy_socket: str = PROXY_SOCKET
    proxy_port: int = PROXY_PORT
    issue_id: int | None = None


@dataclass(frozen=True)
class ContractProcessParams:
    """Output of contract translation: CLI args (secrets by name only) and subprocess env (secret values)."""

    args: tuple[str, ...]
    env: dict[str, str]


class ContractTranslator(abc.ABC):
    """Port for translating a ContractSpec into engine-specific process parameters."""

    @abc.abstractmethod
    def translate(self, spec: ContractSpec) -> ContractProcessParams: ...
