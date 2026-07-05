"""
ProcessRunner port and adapters: ProcessHandle/ProcessRunner ports plus subprocess-backed implementations.
"""

import abc
import subprocess

from ..common import AddaDevError


class ProcessError(AddaDevError):
    """Raised when an OS-level subprocess operation fails."""


class ProcessRunError(AddaDevError):
    """Raised when a subprocess exits with a non-zero status."""


class ProcessHandle(abc.ABC):
    """Handle to a running or completed subprocess."""

    def __init__(self, cmd: list[str]) -> None:
        self._cmd = cmd

    @abc.abstractmethod
    def wait(self) -> int:
        """Block until the process exits and return its exit code. Idempotent."""

    @abc.abstractmethod
    def terminate(self) -> None:
        """Send SIGTERM to the process."""

    @abc.abstractmethod
    def stdout(self) -> str:
        """Return captured stdout."""

    @abc.abstractmethod
    def stderr(self) -> str:
        """Return captured stderr."""

    def raise_if_failed(self, message: str) -> None:
        """Wait for the process; raise ProcessRunError if exit code is non-zero."""
        code = self.wait()
        if code == 0:
            return
        try:
            out: str | None = self.stdout().strip() or None
        except RuntimeError:
            out = None
        try:
            err: str | None = self.stderr().strip() or None
        except RuntimeError:
            err = None
        raise ProcessRunError(message, command=" ".join(self._cmd), code=str(code), stdout=out, stderr=err)


class ProcessRunner(abc.ABC):
    """Port for launching subprocesses."""

    @abc.abstractmethod
    def run(self, cmd: list[str], env: dict[str, str] | None = None) -> ProcessHandle:
        """Launch cmd and return a handle to the running process."""


class _DefaultHandle(ProcessHandle):
    """ProcessHandle for DefaultRunner — stdout and stderr are not captured."""

    def __init__(self, process: subprocess.Popen[bytes], cmd: list[str]) -> None:
        super().__init__(cmd)
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
        return _DefaultHandle(process, cmd)


class _CapturedHandle(ProcessHandle):
    """ProcessHandle for CapturedOutputRunner — stdout and stderr are captured after wait()."""

    def __init__(self, process: subprocess.Popen[str], cmd: list[str]) -> None:
        super().__init__(cmd)
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
        if self._stdout is None:
            raise RuntimeError("stdout was not captured")
        return self._stdout

    def stderr(self) -> str:
        if self._returncode is None:
            raise RuntimeError("stderr is not available before wait()")
        if self._stderr is None:
            raise RuntimeError("stderr was not captured")
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
        return _CapturedHandle(process, cmd)
