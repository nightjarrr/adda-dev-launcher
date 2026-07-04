"""
ProxySidecar port: abstract interface for an egress proxy sidecar.
"""

import abc
from pathlib import Path

from ..common import AddaDevError
from .session import Session


class ProxyError(AddaDevError):
    """Raised when the proxy sidecar fails to start, times out, or exits unexpectedly."""

    def __init__(self, message: str, *, stdout: str | None = None, stderr: str | None = None) -> None:
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr
        if stdout:
            self.details.append(("stdout", stdout))
        if stderr:
            self.details.append(("stderr", stderr))


class ProxySidecar(abc.ABC):
    """Abstract port for starting and stopping an egress proxy sidecar."""

    @abc.abstractmethod
    def start(self, session: Session) -> Path:
        """Start the sidecar for the given session and return the host-side socket path when it is ready."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop and remove the sidecar, best-effort. Safe to call before start() completes."""
