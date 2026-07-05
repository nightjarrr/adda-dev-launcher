"""
ProxySidecar port: abstract interface for an egress proxy sidecar.
"""

import abc
from pathlib import Path

from ..common import AddaDevError
from .session import Session
from .window import Window


class ProxyError(AddaDevError):
    """Raised when the proxy sidecar fails to start, times out, or exits unexpectedly."""


class ProxySidecar(abc.ABC):
    """Abstract port for starting and stopping an egress proxy sidecar."""

    @abc.abstractmethod
    def start(self, session: Session) -> Path:
        """Start the sidecar for the given session and return the host-side socket path when it is ready."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop and remove the sidecar, best-effort. Safe to call before start() completes."""

    @abc.abstractmethod
    def watch_logs(self, window: Window) -> None:
        """Stream sidecar logs into the given window."""
