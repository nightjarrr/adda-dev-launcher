"""
ProcessRunner port and ProcessHandle port for subprocess execution.
"""

import abc

from ..common import AddaDevError


class ProcessError(AddaDevError):
    """Raised when an OS-level subprocess operation fails."""


class ProcessHandle(abc.ABC):
    """Handle to a running or completed subprocess."""

    @abc.abstractmethod
    def wait(self) -> int:
        """Block until the process exits and return its exit code. Idempotent."""

    @abc.abstractmethod
    def terminate(self) -> None:
        """Send SIGTERM to the process."""

    @abc.abstractmethod
    def stdout(self) -> str:
        """Return captured stdout."""

    @abc.abstractmethod
    def stderr(self) -> str:
        """Return captured stderr."""


class ProcessRunner(abc.ABC):
    """Port for launching subprocesses."""

    @abc.abstractmethod
    def run(self, cmd: list[str], env: dict[str, str] | None = None) -> ProcessHandle:
        """Launch cmd and return a handle to the running process."""
