"""
Tests for adda_dev.infra.process: DefaultRunner and CapturedOutputRunner.
"""

import pytest

from adda_dev.domain.process import ProcessError, ProcessHandle
from adda_dev.infra.process import CapturedOutputRunner, DefaultRunner

# ---------------------------------------------------------------------------
# DefaultRunner / _DefaultHandle
# ---------------------------------------------------------------------------


def test_defaultrunner_start_returns_handle() -> None:
    runner = DefaultRunner()
    handle = runner.run(["true"])
    assert isinstance(handle, ProcessHandle)
    handle.wait()


def test_defaultrunner_wait_returns_zero_on_success() -> None:
    runner = DefaultRunner()
    handle = runner.run(["true"])
    assert handle.wait() == 0


def test_defaultrunner_wait_returns_nonzero_on_failure() -> None:
    runner = DefaultRunner()
    handle = runner.run(["false"])
    assert handle.wait() != 0


def test_defaultrunner_wait_is_idempotent() -> None:
    runner = DefaultRunner()
    handle = runner.run(["true"])
    assert handle.wait() == 0
    assert handle.wait() == 0


def test_defaultrunner_stdout_raises() -> None:
    runner = DefaultRunner()
    handle = runner.run(["true"])
    handle.wait()
    with pytest.raises(RuntimeError):
        handle.stdout()


def test_defaultrunner_stderr_raises() -> None:
    runner = DefaultRunner()
    handle = runner.run(["true"])
    handle.wait()
    with pytest.raises(RuntimeError):
        handle.stderr()


def test_defaultrunner_terminate_exits_process() -> None:
    runner = DefaultRunner()
    handle = runner.run(["sleep", "infinity"])
    handle.terminate()
    assert handle.wait() != 0


def test_defaultrunner_env_none_inherits_environment() -> None:
    runner = DefaultRunner()
    handle = runner.run(["env"], env=None)
    assert handle.wait() == 0


def test_defaultrunner_start_raises_processerror_on_bad_command() -> None:
    runner = DefaultRunner()
    with pytest.raises(ProcessError):
        runner.run(["/nonexistent"])


# ---------------------------------------------------------------------------
# CapturedOutputRunner / _CapturedHandle
# ---------------------------------------------------------------------------


def test_capturedoutputrunner_start_returns_handle() -> None:
    runner = CapturedOutputRunner()
    handle = runner.run(["true"])
    assert isinstance(handle, ProcessHandle)
    handle.wait()


def test_capturedoutputrunner_wait_returns_zero_on_success() -> None:
    runner = CapturedOutputRunner()
    handle = runner.run(["true"])
    assert handle.wait() == 0


def test_capturedoutputrunner_wait_returns_nonzero_on_failure() -> None:
    runner = CapturedOutputRunner()
    handle = runner.run(["false"])
    assert handle.wait() != 0


def test_capturedoutputrunner_wait_is_idempotent() -> None:
    runner = CapturedOutputRunner()
    handle = runner.run(["true"])
    assert handle.wait() == 0
    assert handle.wait() == 0


def test_capturedoutputrunner_stdout_returns_captured_output() -> None:
    runner = CapturedOutputRunner()
    handle = runner.run(["echo", "hello"])
    handle.wait()
    assert handle.stdout() is not None
    assert "hello" in handle.stdout()  # type: ignore[operator]


def test_capturedoutputrunner_stderr_returns_empty_for_stdout_only_command() -> None:
    runner = CapturedOutputRunner()
    handle = runner.run(["echo", "hello"])
    handle.wait()
    assert handle.stderr() == ""


def test_capturedoutputrunner_stdout_raises_before_wait() -> None:
    runner = CapturedOutputRunner()
    handle = runner.run(["true"])
    with pytest.raises(RuntimeError):
        handle.stdout()
    handle.wait()


def test_capturedoutputrunner_stderr_raises_before_wait() -> None:
    runner = CapturedOutputRunner()
    handle = runner.run(["true"])
    with pytest.raises(RuntimeError):
        handle.stderr()
    handle.wait()


def test_capturedoutputrunner_terminate_exits_process() -> None:
    runner = CapturedOutputRunner()
    handle = runner.run(["sleep", "infinity"])
    handle.terminate()
    assert handle.wait() != 0


def test_capturedoutputrunner_env_none_inherits_environment() -> None:
    runner = CapturedOutputRunner()
    handle = runner.run(["env"], env=None)
    assert handle.wait() == 0


def test_capturedoutputrunner_start_raises_processerror_on_bad_command() -> None:
    runner = CapturedOutputRunner()
    with pytest.raises(ProcessError):
        runner.run(["/nonexistent"])
