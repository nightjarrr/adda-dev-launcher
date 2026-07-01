"""
SessionManager port and Window ABC: host-side session lifecycle base classes.
"""

import abc
import os

from ..common import Output
from ..domain.contract import ContractSpec, ContractTranslator
from ..domain.session import Session, SessionRepository


class Window(abc.ABC):
    """Abstract window within a session — owns the process lifecycle for one pane."""

    def __init__(self, name: str) -> None:
        self.name = name

    @abc.abstractmethod
    def run(self, cmd: list[str], env: dict[str, str]) -> None:
        """Start the process; the window stores the handle internally."""

    @abc.abstractmethod
    def attach(self) -> None:
        """Block until the window exits."""

    @abc.abstractmethod
    def close(self) -> None:
        """Tear down the window."""


class SessionManager(abc.ABC):
    """Base class for session lifecycle management: create, run primary window, teardown."""

    def __init__(
        self,
        session_repo: SessionRepository,
        translator: ContractTranslator,
        output: Output,
    ) -> None:
        self._repo = session_repo
        self._translator = translator
        self._output = output
        self._windows: list[Window] = []
        self._session: Session | None = None

    def launch(self, project_name: str, spec: ContractSpec) -> Session:
        """Create a session, open the primary window, run the command, and block until it exits."""
        session = self._repo.create(project_name, spec.issue_id)
        self._session = session
        params = self._translator.translate(spec)
        full_env = {**os.environ, **params.env}
        self._output.info(f"Session:  {session.session_id}")
        self._output.info(f"Command:  {' '.join(params.args)}")
        primary = self.create_window("adda-dev primary")
        self._windows.append(primary)
        self._open_secondary_windows(session, spec)
        primary.run(list(params.args), full_env)
        primary.attach()
        return session

    def terminate(self, session: Session) -> None:
        """Close all tracked windows, run teardown hook, then delete the session record."""
        for window in self._windows:
            window.close()
        self._teardown(session)
        self._repo.delete(session)

    @abc.abstractmethod
    def create_window(self, name: str) -> Window:
        """Return a new Window for the given session name."""

    def _open_secondary_windows(self, session: Session, spec: ContractSpec) -> None:
        """Hook: open extra windows (e.g. shell, logs). No-op for Direct mode."""

    def _teardown(self, session: Session) -> None:
        """Hook: perform mode-specific teardown (e.g. kill tmux server). No-op for Direct mode."""
