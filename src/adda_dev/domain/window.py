"""
Window ABC and WindowedRunner bridge: session window abstractions for running processes into panes.
"""

import abc

from .process import ProcessHandle, ProcessRunner


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
