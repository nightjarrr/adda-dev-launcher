"""
Tests for adda_dev.infra.window: WindowedRunner and _WindowHandle.
"""

import pytest

from adda_dev.domain.window import Window
from adda_dev.infra.window import WindowedRunner, _WindowHandle


class _FakeWindow(Window):
    """Window test double that records open/attach/close calls."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.open_calls: list[tuple[list[str], dict[str, str] | None]] = []
        self.attached: int = 0
        self.closed: int = 0

    def open(self, cmd: list[str], env: dict[str, str] | None = None) -> None:
        self.open_calls.append((cmd, env))

    def attach(self) -> None:
        self.attached += 1

    def close(self) -> None:
        self.closed += 1


def test_windowedrunner_run_calls_window_open() -> None:
    window = _FakeWindow("test")
    runner = WindowedRunner(window)
    runner.run(["docker", "run"], {"ENV": "val"})
    assert len(window.open_calls) == 1
    assert window.open_calls[0] == (["docker", "run"], {"ENV": "val"})


def test_windowedrunner_run_returns_window_handle() -> None:
    window = _FakeWindow("test")
    runner = WindowedRunner(window)
    handle = runner.run(["true"])
    assert isinstance(handle, _WindowHandle)


def test_windowhandle_wait_calls_attach_and_returns_0() -> None:
    window = _FakeWindow("test")
    handle = _WindowHandle(window)
    result = handle.wait()
    assert result == 0
    assert window.attached == 1


def test_windowhandle_terminate_calls_close() -> None:
    window = _FakeWindow("test")
    handle = _WindowHandle(window)
    handle.terminate()
    assert window.closed == 1


def test_windowhandle_stdout_raises() -> None:
    window = _FakeWindow("test")
    handle = _WindowHandle(window)
    with pytest.raises(RuntimeError):
        handle.stdout()


def test_windowhandle_stderr_raises() -> None:
    window = _FakeWindow("test")
    handle = _WindowHandle(window)
    with pytest.raises(RuntimeError):
        handle.stderr()
