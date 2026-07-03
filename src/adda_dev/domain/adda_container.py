"""
AddaPrimaryContainer port: abstract interface for the primary ADDA container lifecycle.
"""

import abc

from .contract import ContractSpec
from .session import Session
from .window import Window


class AddaPrimaryContainer(abc.ABC):
    """Abstract port for starting and stopping the primary ADDA runtime container."""

    @abc.abstractmethod
    def start(self, session: Session, spec: ContractSpec, window: Window) -> None:
        """Translate spec, pull the image, and run the container interactively into the given window.

        Sets the container name from session.session_id before any I/O so that stop()
        covers any failure that occurs after this point.
        """

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop and remove the primary container, best-effort.

        Safe to call before start() completes (no-op). Tolerant of the container already
        being gone (e.g. removed by --rm when the session exited cleanly).
        """
