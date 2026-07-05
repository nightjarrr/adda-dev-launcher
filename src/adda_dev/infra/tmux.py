"""
TmuxServer and TmuxSession adapters: low-level tmux CLI wrappers for the adda-dev session layer.
"""

import importlib.resources
import os
from pathlib import Path

from ..common import AddaDevError
from ..domain.session import Session
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
        handle = self._runner.run(
            ["tmux", "-L", TMUX_SERVER_NAME, "new-window", "-t", self._session_name, "-n", window_name, *cmd]
        )
        if handle.wait() != 0:
            raise TmuxError(f"tmux new-window failed: {handle.stderr().strip()}")

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
        handle = self._runner.run(
            [
                "tmux",
                "-L",
                TMUX_SERVER_NAME,
                "-f",
                str(_BUNDLED_CONFIG),
                "new-session",
                "-d",
                "-s",
                session_name,
                "-n",
                window_name,
                *cmd,
            ]
        )
        if handle.wait() != 0:
            raise TmuxError(f"tmux new-session failed: {handle.stderr().strip()}")
        return TmuxSession(session_name)

    def kill_server(self) -> None:
        """Kill the adda-dev tmux server, best-effort."""
        try:
            handle = self._runner.run(["tmux", "-L", TMUX_SERVER_NAME, "kill-server"])
            handle.wait()
        except Exception:  # noqa: BLE001
            pass
