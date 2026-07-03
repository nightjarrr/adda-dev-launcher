"""
Window ABC: session window abstraction for running a process into a pane.
"""

import abc


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
