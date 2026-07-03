"""
ContainerEngine port: abstract interface for container lifecycle operations.
"""

import abc

from ..common import AddaDevError
from ..domain.process import ProcessHandle, ProcessRunner


class ContainerEngineUnavailableError(AddaDevError):
    """Raised when the container engine binary is missing or the daemon is unreachable."""


class ContainerEngine(abc.ABC):
    """Abstract port for executing container lifecycle operations."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Return the engine's short name."""

    @property
    @abc.abstractmethod
    def version(self) -> str:
        """Return the server version string reported by the engine."""

    @property
    @abc.abstractmethod
    def rootless(self) -> bool:
        """Return True when the engine daemon is running in rootless mode."""

    @abc.abstractmethod
    def pull(self, runner: ProcessRunner, image: str) -> ProcessHandle:
        """Pull an image from a registry."""

    @abc.abstractmethod
    def run_it(
        self,
        runner: ProcessRunner,
        image: str,
        name: str,
        args: list[str],
        env: dict[str, str] | None = None,
        cmd: list[str] | None = None,
        remove: bool = False,
    ) -> ProcessHandle:
        """Run an interactive (attached) container."""

    @abc.abstractmethod
    def run_d(
        self,
        runner: ProcessRunner,
        image: str,
        name: str,
        args: list[str],
        env: dict[str, str] | None = None,
        cmd: list[str] | None = None,
        remove: bool = False,
    ) -> ProcessHandle:
        """Run a detached container."""

    @abc.abstractmethod
    def stop(self, runner: ProcessRunner, name: str) -> ProcessHandle:
        """Stop a running container by name."""

    @abc.abstractmethod
    def exec(self, runner: ProcessRunner, name: str, cmd: list[str]) -> ProcessHandle:
        """Execute a command in a running container (non-interactive)."""

    @abc.abstractmethod
    def exec_it(self, runner: ProcessRunner, name: str, cmd: list[str]) -> ProcessHandle:
        """Execute a command in a running container (interactive)."""

    @abc.abstractmethod
    def logs_f(self, runner: ProcessRunner, name: str) -> ProcessHandle:
        """Stream logs from a running container (follow mode)."""

    @abc.abstractmethod
    def inspect(self, runner: ProcessRunner, name: str) -> ProcessHandle:
        """Inspect a container and return its JSON metadata."""

    @abc.abstractmethod
    def rm(self, runner: ProcessRunner, name: str, force: bool = False) -> ProcessHandle:
        """Remove a container by name. Pass force=True to remove a running container."""

    @abc.abstractmethod
    def logs(self, runner: ProcessRunner, name: str) -> ProcessHandle:
        """Capture a one-shot snapshot of container logs."""
