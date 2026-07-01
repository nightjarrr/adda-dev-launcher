"""
ProcessRunner infrastructure: subprocess-backed process runners.
"""

import subprocess

from ..domain.process import ProcessError, ProcessHandle, ProcessRunner


class _DefaultHandle(ProcessHandle):
    """ProcessHandle for DefaultRunner — stdout and stderr are not captured."""

    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self._process = process
        self._returncode: int | None = None

    def wait(self) -> int:
        if self._returncode is None:
            try:
                self._returncode = self._process.wait()
            except OSError as exc:
                raise ProcessError(str(exc)) from exc
        return self._returncode

    def terminate(self) -> None:
        try:
            self._process.terminate()
        except OSError as exc:
            raise ProcessError(str(exc)) from exc

    def stdout(self) -> str:
        raise RuntimeError("DefaultRunner does not capture stdout")

    def stderr(self) -> str:
        raise RuntimeError("DefaultRunner does not capture stderr")


class DefaultRunner(ProcessRunner):
    """ProcessRunner that launches processes without redirecting stdout or stderr."""

    def run(self, cmd: list[str], env: dict[str, str] | None = None) -> ProcessHandle:
        try:
            process: subprocess.Popen[bytes] = subprocess.Popen(cmd, env=env)
        except OSError as exc:
            raise ProcessError(str(exc)) from exc
        return _DefaultHandle(process)


class _CapturedHandle(ProcessHandle):
    """ProcessHandle for CapturedOutputRunner — stdout and stderr are captured after wait()."""

    def __init__(self, process: subprocess.Popen[str]) -> None:
        self._process = process
        self._returncode: int | None = None
        self._stdout: str | None = None
        self._stderr: str | None = None

    def wait(self) -> int:
        if self._returncode is None:
            try:
                stdout, stderr = self._process.communicate()
            except OSError as exc:
                raise ProcessError(str(exc)) from exc
            self._stdout = stdout
            self._stderr = stderr
            self._returncode = self._process.returncode
        return self._returncode

    def terminate(self) -> None:
        try:
            self._process.terminate()
        except OSError as exc:
            raise ProcessError(str(exc)) from exc

    def stdout(self) -> str:
        if self._returncode is None:
            raise RuntimeError("stdout is not available before wait()")
        assert self._stdout is not None
        return self._stdout

    def stderr(self) -> str:
        if self._returncode is None:
            raise RuntimeError("stderr is not available before wait()")
        assert self._stderr is not None
        return self._stderr


class CapturedOutputRunner(ProcessRunner):
    """ProcessRunner that captures stdout and stderr from launched processes."""

    def run(self, cmd: list[str], env: dict[str, str] | None = None) -> ProcessHandle:
        try:
            process: subprocess.Popen[str] = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as exc:
            raise ProcessError(str(exc)) from exc
        return _CapturedHandle(process)
