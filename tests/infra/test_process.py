"""
Tests for adda_dev.infra.process: DefaultRunner and CapturedOutputRunner.
"""

import pytest

from adda_dev.infra.process import CapturedOutputRunner, DefaultRunner, ProcessError, ProcessHandle, ProcessRunError

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


# ---------------------------------------------------------------------------
# raise_if_failed — CapturedOutputRunner
# ---------------------------------------------------------------------------


def test_capturedoutputrunner_raise_if_failed_nonzero_raises_processrunerror() -> None:
    runner = CapturedOutputRunner()
    handle = runner.run(["false"])
    with pytest.raises(ProcessRunError):
        handle.raise_if_failed("command failed")


def test_capturedoutputrunner_raise_if_failed_nonzero_details_include_command() -> None:
    runner = CapturedOutputRunner()
    handle = runner.run(["false"])
    with pytest.raises(ProcessRunError) as exc_info:
        handle.raise_if_failed("command failed")
    detail_keys = [k for k, _ in exc_info.value.details]
    assert "command" in detail_keys


def test_capturedoutputrunner_raise_if_failed_nonzero_details_include_code() -> None:
    runner = CapturedOutputRunner()
    handle = runner.run(["false"])
    with pytest.raises(ProcessRunError) as exc_info:
        handle.raise_if_failed("command failed")
    detail_keys = [k for k, _ in exc_info.value.details]
    assert "code" in detail_keys


def test_capturedoutputrunner_raise_if_failed_nonzero_details_command_value() -> None:
    runner = CapturedOutputRunner()
    handle = runner.run(["sh", "-c", "exit 1"])
    with pytest.raises(ProcessRunError) as exc_info:
        handle.raise_if_failed("command failed")
    detail_map = dict(exc_info.value.details)
    assert detail_map["command"] == "sh -c exit 1"


def test_capturedoutputrunner_raise_if_failed_nonzero_details_stdout_and_stderr_present() -> None:
    runner = CapturedOutputRunner()
    handle = runner.run(["sh", "-c", "echo OUT; echo ERR >&2; exit 1"])
    with pytest.raises(ProcessRunError) as exc_info:
        handle.raise_if_failed("command failed")
    detail_keys = [k for k, _ in exc_info.value.details]
    assert "stdout" in detail_keys
    assert "stderr" in detail_keys


def test_capturedoutputrunner_raise_if_failed_zero_returns_none() -> None:
    runner = CapturedOutputRunner()
    handle = runner.run(["true"])
    result = handle.raise_if_failed("command failed")
    assert result is None


# ---------------------------------------------------------------------------
# raise_if_failed — DefaultRunner
# ---------------------------------------------------------------------------


def test_defaultrunner_raise_if_failed_nonzero_raises_processrunerror() -> None:
    runner = DefaultRunner()
    handle = runner.run(["false"])
    with pytest.raises(ProcessRunError):
        handle.raise_if_failed("command failed")


def test_defaultrunner_raise_if_failed_nonzero_details_include_command_and_code() -> None:
    runner = DefaultRunner()
    handle = runner.run(["false"])
    with pytest.raises(ProcessRunError) as exc_info:
        handle.raise_if_failed("command failed")
    detail_keys = [k for k, _ in exc_info.value.details]
    assert "command" in detail_keys
    assert "code" in detail_keys


def test_defaultrunner_raise_if_failed_nonzero_details_no_stdout_or_stderr() -> None:
    runner = DefaultRunner()
    handle = runner.run(["false"])
    with pytest.raises(ProcessRunError) as exc_info:
        handle.raise_if_failed("command failed")
    detail_keys = [k for k, _ in exc_info.value.details]
    assert "stdout" not in detail_keys
    assert "stderr" not in detail_keys
