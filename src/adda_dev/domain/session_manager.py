"""
SessionManager port and Window ABC: host-side session lifecycle base classes.
"""

import abc
import os

from ..common import Output
from ..domain.container import ContainerEngine
from ..domain.contract import ContractSpec, ContractSpecDraft, ContractTranslator
from ..domain.process import ProcessHandle, ProcessRunner
from ..domain.proxy import ProxySidecar
from ..domain.session import Session, SessionRepository


class Window(abc.ABC):
    """Abstract window within a session — owns the process lifecycle for one pane."""

    def __init__(self, name: str) -> None:
        self.name = name

    @abc.abstractmethod
    def open(self, cmd: list[str], env: dict[str, str] | None = None) -> None:
        """Start the process; the window stores the handle internally."""

    @abc.abstractmethod
    def attach(self) -> None:
        """Block until the window exits."""

    @abc.abstractmethod
    def close(self) -> None:
        """Tear down the window."""


class _WindowHandle(ProcessHandle):
    """ProcessHandle that delegates wait/terminate to a Window."""

    def __init__(self, window: Window) -> None:
        self._window = window

    def wait(self) -> int:
        self._window.attach()
        return 0

    def terminate(self) -> None:
        self._window.close()

    def stdout(self) -> str:
        raise RuntimeError("WindowedRunner does not capture stdout — output goes to the terminal")

    def stderr(self) -> str:
        raise RuntimeError("WindowedRunner does not capture stderr — output goes to the terminal")


class WindowedRunner(ProcessRunner):
    """Adapts a session Window to the ProcessRunner port so the engine can run into it."""

    def __init__(self, window: Window) -> None:
        self._window = window

    def run(self, cmd: list[str], env: dict[str, str] | None = None) -> ProcessHandle:
        self._window.open(cmd, env)
        return _WindowHandle(self._window)


class SessionManager(abc.ABC):
    """Base class for session lifecycle management: create, run primary window, teardown."""

    def __init__(
        self,
        session_repo: SessionRepository,
        translator: ContractTranslator,
        engine: ContainerEngine,
        runner: ProcessRunner,
        output: Output,
        sidecar: ProxySidecar,
    ) -> None:
        self._repo = session_repo
        self._translator = translator
        self._engine = engine
        self._runner = runner
        self._output = output
        self._sidecar = sidecar
        self._windows: list[Window] = []
        self._session: Session | None = None

    def run(self, project_name: str, draft: ContractSpecDraft) -> None:
        """Launch a session and guarantee teardown even when launch raises."""
        try:
            self.launch(project_name, draft)
        finally:
            self.terminate()

    def launch(self, project_name: str, draft: ContractSpecDraft) -> None:
        """Create a session, start the sidecar, pull and run the main container."""
        session = self._repo.create(project_name, draft.issue_id)
        self._session = session
        host_socket = self._sidecar.start(session.runtime_dir)
        spec = draft.with_session(host_socket)
        params = self._translator.translate(spec)
        full_env = {**os.environ, **params.env}
        self._output.info(f"Session:  {session.session_id}")
        self._engine.pull(self._runner, spec.image).wait()
        primary = self.create_window("adda-dev primary")
        self._windows.append(primary)
        self._engine.run_it(WindowedRunner(primary), spec.image, session.session_id, list(params.args), full_env, remove=True)
        self._open_secondary_windows(session, spec)
        primary.attach()

    def terminate(self) -> None:
        """Close all tracked windows, run teardown hook, stop sidecar, then delete the session record."""
        for window in self._windows:
            window.close()
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
