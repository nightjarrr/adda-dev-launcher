"""
TmuxServer and TmuxSession adapters: low-level tmux CLI wrappers for the adda-dev session layer.
"""

import importlib.resources
import os
from pathlib import Path

from ..common import AddaDevError, Output
from ..domain.adda_container import AddaPrimaryContainer
from ..domain.contract import ContractSpec
from ..domain.proxy import ProxySidecar
from ..domain.session import Session, SessionRepository
from ..domain.session_manager import SessionManager
from ..domain.window import Window
from .config import TmuxSessionConfig
from .process import CapturedOutputRunner, DefaultRunner, ProcessError

TMUX_SERVER_NAME = "adda-dev"

_BUNDLED_CONFIG: Path = Path(str(importlib.resources.files("adda_dev") / "data" / "adda-dev.tmux.conf"))


class TmuxError(AddaDevError):
    """Raised when a tmux CLI operation fails."""


class TmuxSession:
    """Session-scoped tmux CLI adapter."""

    def __init__(self, session_name: str) -> None:
        self._session_name = session_name
        self._runner = CapturedOutputRunner()

    # Public methods

    def new_window(self, window_name: str, cmd: list[str], env: dict[str, str] | None = None) -> None:
        """Open a new window in this session running cmd."""
        self._runner.run(
            ["tmux", "-L", TMUX_SERVER_NAME, "new-window", "-d", "-t", self._session_name, "-n", window_name, *cmd]
        ).raise_if_failed("tmux new-window failed")

    def kill_window(self, window_name: str) -> None:
        """Kill a window by name, best-effort."""
        try:
            handle = self._runner.run(
                ["tmux", "-L", TMUX_SERVER_NAME, "kill-window", "-t", f"{self._session_name}:{window_name}"]
            )
            handle.wait()
        except Exception:  # noqa: BLE001
            pass

    def attach(self) -> None:
        """Attach to this session, inheriting stdio."""
        handle = DefaultRunner().run(["tmux", "-L", TMUX_SERVER_NAME, "attach-session", "-t", self._session_name])
        handle.wait()

    def kill(self) -> None:
        """Kill this session, best-effort."""
        try:
            handle = self._runner.run(["tmux", "-L", TMUX_SERVER_NAME, "kill-session", "-t", self._session_name])
            handle.wait()
        except Exception:  # noqa: BLE001
            pass


class TmuxServer:
    """Server-scoped tmux CLI adapter; validates tmux availability on construction."""

    def __init__(self) -> None:
        self._runner = CapturedOutputRunner()
        try:
            handle = self._runner.run(["tmux", "-V"])
            code = handle.wait()
        except ProcessError as exc:
            raise TmuxError(f"tmux CLI not found or not executable: {exc}") from exc
        if code != 0:
            raise TmuxError(f"tmux is not available: {handle.stderr().strip()}")
        self._version = handle.stdout().strip().removeprefix("tmux ").strip()

    # Properties

    @property
    def version(self) -> str:
        """Return the tmux version string."""
        return self._version

    # Public methods

    def ensure_no_reentry(self) -> None:
        """Raise TmuxError if the process is already running inside an adda-dev tmux session."""
        tmux_env = os.environ.get("TMUX", "")
        if not tmux_env:
            return
        socket_path = tmux_env.split(",")[0]
        if Path(socket_path).name == TMUX_SERVER_NAME:
            raise TmuxError(
                "adda-dev does not support running from inside an adda-dev tmux session. "
                "Detach from the current session before launching."
            )

    def new_session(self, session: Session, window_name: str, cmd: list[str], env: dict[str, str] | None = None) -> TmuxSession:
        """Create a new detached tmux session and return a TmuxSession handle."""
        session_name = session.session_id
        tmux_cmd = ["tmux", "-L", TMUX_SERVER_NAME, "-f", str(_BUNDLED_CONFIG)]
        if env:
            keys_str = " ".join(env.keys())
            tmux_cmd += ["set-option", "-g", "update-environment", keys_str, ";"]
        tmux_cmd += ["new-session", "-d", "-s", session_name, "-n", window_name, *cmd]
        self._runner.run(tmux_cmd, env).raise_if_failed("tmux new-session failed")
        return TmuxSession(session_name)

    def kill_server(self) -> None:
        """Kill the adda-dev tmux server, best-effort."""
        try:
            handle = self._runner.run(["tmux", "-L", TMUX_SERVER_NAME, "kill-server"])
            handle.wait()
        except Exception:  # noqa: BLE001
            pass


class TmuxSessionManager(SessionManager):
    """SessionManager that creates a tmux session for the primary window and tears it down on exit."""

    def __init__(
        self,
        server: TmuxServer,
        session_repo: SessionRepository,
        output: Output,
        sidecar: ProxySidecar,
        container: AddaPrimaryContainer,
        tmux_config: TmuxSessionConfig = TmuxSessionConfig(),
    ) -> None:
        super().__init__(session_repo, output, sidecar, container)
        self._server = server
        self._tmux_session: TmuxSession | None = None
        self._tmux_config = tmux_config
        output.kv("tmux", server.version)
        self._server.ensure_no_reentry()

    def _set_tmux_session(self, session: TmuxSession) -> None:
        self._tmux_session = session

    def _create_window(self, name: str) -> Window:
        if self._tmux_session is None:
            return TmuxPrimaryWindow(name, self._server, self._session, self, self._output)
        return TmuxWindow(name, self._tmux_session)

    def _open_secondary_windows(self, session: Session, spec: ContractSpec) -> None:
        if self._tmux_config.shell_window:
            shell_window = self.create_window("adda-dev shell")
            self._container.exec_interactive_shell(shell_window)
        if self._tmux_config.proxy_logs_window:
            logs_window = self.create_window("adda-dev proxy logs")
            self._sidecar.watch_logs(logs_window)

    def _teardown(self) -> None:
        if self._tmux_session is not None:
            with self._output.step("tmux session") as s:
                self._tmux_session.kill()
                s.done("stopped")


class TmuxPrimaryWindow(Window):
    """Primary window created by TmuxSessionManager; open() creates the tmux session."""

    def __init__(
        self,
        name: str,
        server: TmuxServer,
        domain_session: Session | None,
        manager: TmuxSessionManager,
        output: Output,
    ) -> None:
        super().__init__(name)
        self._server = server
        self._domain_session = domain_session
        self._manager = manager
        self._output = output
        self._tmux: TmuxSession | None = None

    def open(self, cmd: list[str], env: dict[str, str] | None = None) -> None:
        if self._domain_session is None:
            raise TmuxError("open() called before session was initialized")
        with self._output.step("tmux session") as s:
            script_path = self._domain_session.runtime_dir / "run-primary-window.sh"
            script_path.write_text(
                f'#!/bin/bash\n"$@"\ntmux -L {TMUX_SERVER_NAME} kill-session -t {self._domain_session.session_id}\n'
            )
            script_path.chmod(0o755)
            self._tmux = self._server.new_session(self._domain_session, self.name, [str(script_path), *cmd], env)
            s.done("started")
        self._manager._set_tmux_session(self._tmux)

    def attach(self) -> None:
        if self._tmux is None:
            raise TmuxError("attach() called before open()")
        self._tmux.attach()

    def close(self) -> None:
        if self._tmux is not None:
            self._tmux.kill_window(self.name)


class TmuxWindow(Window):
    """Secondary window added to an existing tmux session."""

    def __init__(self, name: str, tmux_session: TmuxSession) -> None:
        super().__init__(name)
        self._tmux = tmux_session

    def open(self, cmd: list[str], env: dict[str, str] | None = None) -> None:
        self._tmux.new_window(self.name, cmd, env)

    def attach(self) -> None:
        self._tmux.attach()

    def close(self) -> None:
        self._tmux.kill_window(self.name)
