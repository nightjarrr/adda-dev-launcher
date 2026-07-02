"""
ProxySidecar port: abstract interface for an egress proxy sidecar.
"""

import abc
from pathlib import Path

from ..common import AddaDevError


class ProxyError(AddaDevError):
    """Raised when the proxy sidecar fails to start, times out, or exits unexpectedly."""


class ProxySidecar(abc.ABC):
    """Abstract port for starting and stopping an egress proxy sidecar."""

    @abc.abstractmethod
    def start(self, runtime_dir: Path) -> Path:
        """Start the sidecar and return the host-side socket path when it is ready."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop and remove the sidecar, best-effort. Safe to call before start() completes."""
