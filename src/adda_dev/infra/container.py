"""
ContainerEngine port, DockerEngine adapter, and create_engine() factory.
"""

import abc
import os

from ..common import AddaDevError, Output
from .config import ContainerEngineChoice
from .process import CapturedOutputRunner, ProcessError, ProcessHandle, ProcessRunner

_BIN = "docker"


class ContainerEngineUnavailableError(AddaDevError):
    """Raised when the container engine binary is missing or the daemon is unreachable."""


class ContainerEngine(abc.ABC):
    """Abstract port for executing container lifecycle operations."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Return the engine's short name."""

    @property
    @abc.abstractmethod
    def version(self) -> str:
        """Return the server version string reported by the engine."""

    @property
    @abc.abstractmethod
    def rootless(self) -> bool:
        """Return True when the engine daemon is running in rootless mode."""

    @abc.abstractmethod
    def pull(self, runner: ProcessRunner, image: str) -> ProcessHandle:
        """Pull an image from a registry."""

    @abc.abstractmethod
    def run_it(
        self,
        runner: ProcessRunner,
        image: str,
        name: str,
        args: list[str],
        env: dict[str, str] | None = None,
        cmd: list[str] | None = None,
        remove: bool = False,
    ) -> ProcessHandle:
        """Run an interactive (attached) container."""

    @abc.abstractmethod
    def run_d(
        self,
        runner: ProcessRunner,
        image: str,
        name: str,
        args: list[str],
        env: dict[str, str] | None = None,
        cmd: list[str] | None = None,
        remove: bool = False,
    ) -> ProcessHandle:
        """Run a detached container."""

    @abc.abstractmethod
    def stop(self, runner: ProcessRunner, name: str) -> ProcessHandle:
        """Stop a running container by name."""

    @abc.abstractmethod
    def exec(self, runner: ProcessRunner, name: str, cmd: list[str]) -> ProcessHandle:
        """Execute a command in a running container (non-interactive)."""

    @abc.abstractmethod
    def exec_it(self, runner: ProcessRunner, name: str, cmd: list[str]) -> ProcessHandle:
        """Execute a command in a running container (interactive)."""

    @abc.abstractmethod
    def logs_f(self, runner: ProcessRunner, name: str) -> ProcessHandle:
        """Stream logs from a running container (follow mode)."""

    @abc.abstractmethod
    def inspect(self, runner: ProcessRunner, name: str) -> ProcessHandle:
        """Inspect a container and return its JSON metadata."""

    @abc.abstractmethod
    def rm(self, runner: ProcessRunner, name: str, force: bool = False) -> ProcessHandle:
        """Remove a container by name. Pass force=True to remove a running container."""

    @abc.abstractmethod
    def logs(self, runner: ProcessRunner, name: str) -> ProcessHandle:
        """Capture a one-shot snapshot of container logs."""


class DockerEngine(ContainerEngine):
    """ContainerEngine adapter that delegates to the docker CLI binary."""

    def __init__(self) -> None:
        runner = CapturedOutputRunner()
        try:
            handle = runner.run([_BIN, "info", "--format", "{{.ServerVersion}}||{{.SecurityOptions}}"])
            code = handle.wait()
        except ProcessError as exc:
            raise ContainerEngineUnavailableError(f"Docker CLI not found or not executable: {exc}") from exc
        if code != 0:
            raise ContainerEngineUnavailableError(f"Docker is not available: {handle.stderr().strip()}")
        version, _, security = handle.stdout().strip().partition("||")
        self._version = version.strip()
        self._rootless = "rootless" in security

    # Properties

    @property
    def name(self) -> str:
        return "docker"

    @property
    def version(self) -> str:
        return self._version

    @property
    def rootless(self) -> bool:
        return self._rootless

    # Lifecycle methods

    def pull(self, runner: ProcessRunner, image: str) -> ProcessHandle:
        return runner.run([_BIN, "pull", image])

    def _run(
        self,
        runner: ProcessRunner,
        mode: str,
        image: str,
        name: str,
        args: list[str],
        env: dict[str, str] | None,
        cmd: list[str] | None,
        remove: bool,
    ) -> ProcessHandle:
        rm = ["--rm"] if remove else []
        merged = {**os.environ, **env} if env is not None else None
        return runner.run([_BIN, "run", mode, *rm, "--name", name, *args, image, *(cmd or [])], merged)

    def run_it(
        self,
        runner: ProcessRunner,
        image: str,
        name: str,
        args: list[str],
        env: dict[str, str] | None = None,
        cmd: list[str] | None = None,
        remove: bool = False,
    ) -> ProcessHandle:
        return self._run(runner, "-it", image, name, args, env, cmd, remove)

    def run_d(
        self,
        runner: ProcessRunner,
        image: str,
        name: str,
        args: list[str],
        env: dict[str, str] | None = None,
        cmd: list[str] | None = None,
        remove: bool = False,
    ) -> ProcessHandle:
        return self._run(runner, "-d", image, name, args, env, cmd, remove)

    def stop(self, runner: ProcessRunner, name: str) -> ProcessHandle:
        return runner.run([_BIN, "stop", name])

    def exec(self, runner: ProcessRunner, name: str, cmd: list[str]) -> ProcessHandle:
        return runner.run([_BIN, "exec", name, *cmd])

    def exec_it(self, runner: ProcessRunner, name: str, cmd: list[str]) -> ProcessHandle:
        return runner.run([_BIN, "exec", "-it", name, *cmd])

    def logs_f(self, runner: ProcessRunner, name: str) -> ProcessHandle:
        return runner.run([_BIN, "logs", "-f", name])

    def inspect(self, runner: ProcessRunner, name: str) -> ProcessHandle:
        return runner.run([_BIN, "inspect", name])

    def rm(self, runner: ProcessRunner, name: str, force: bool = False) -> ProcessHandle:
        args = [_BIN, "rm"]
        if force:
            args.append("-f")
        args.append(name)
        return runner.run(args)

    def logs(self, runner: ProcessRunner, name: str) -> ProcessHandle:
        return runner.run([_BIN, "logs", name])


def create_engine(choice: ContainerEngineChoice, output: Output) -> ContainerEngine:
    """Build the container engine for the given choice, emit startup diagnostic, and return it."""
    if choice is ContainerEngineChoice.docker:
        engine: ContainerEngine = DockerEngine()
    else:
        raise AddaDevError(f"Container engine '{choice.value}' is not supported yet; only 'docker' is available.")
    output.info(f"Engine:   {engine.name} {engine.version} ({'rootless' if engine.rootless else 'root'})")
    if not engine.rootless:
        output.warning(
            f"Running under root {engine.name}; a container escape would hold host-root "
            f"privileges — rootless {engine.name} is recommended."
        )
    return engine
