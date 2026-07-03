"""
SessionManager port: host-side session lifecycle base class.
"""

import abc

from ..common import Output
from .adda_container import AddaPrimaryContainer
from .contract import ContractSpec, ContractSpecDraft
from .proxy import ProxySidecar
from .session import Session, SessionRepository
from .window import Window


class SessionManager(abc.ABC):
    """Base class for session lifecycle management: create, run primary window, teardown."""

    def __init__(
        self,
        session_repo: SessionRepository,
        output: Output,
        sidecar: ProxySidecar,
        container: AddaPrimaryContainer,
    ) -> None:
        self._repo = session_repo
        self._output = output
        self._sidecar = sidecar
        self._container = container
        self._windows: list[Window] = []
        self._session: Session | None = None

    def run(self, project_name: str, draft: ContractSpecDraft) -> None:
        """Launch a session and guarantee teardown even when launch raises."""
        try:
            self._launch(project_name, draft)
        finally:
            self._terminate()

    def _launch(self, project_name: str, draft: ContractSpecDraft) -> None:
        """Create a session, start the sidecar, pull and run the main container."""
        session = self._repo.create(project_name, draft.issue_id)
        self._session = session
        host_socket = self._sidecar.start(session)
        spec = draft.finalize(host_socket)
        self._output.info(f"Session:  {session.session_id}")
        primary = self.create_window("adda-dev primary")
        self._windows.append(primary)
        self._container.start(session, spec, primary)
        self._open_secondary_windows(session, spec)
        primary.attach()

    def _terminate(self) -> None:
        """Close all tracked windows, stop container, run teardown hook, stop sidecar, then delete the session record."""
        for window in self._windows:
            window.close()
        self._container.stop()
        self._teardown()
        self._sidecar.stop()
        if self._session is not None:
            self._repo.delete(self._session)

    @abc.abstractmethod
    def create_window(self, name: str) -> Window:
        """Return a new Window for the given session name."""

    def _open_secondary_windows(self, session: Session, spec: ContractSpec) -> None:
        """Hook: open extra windows (e.g. shell, logs). No-op for Direct mode."""

    def _teardown(self) -> None:
        """Hook: perform mode-specific teardown (e.g. kill tmux server). No-op for Direct mode."""
