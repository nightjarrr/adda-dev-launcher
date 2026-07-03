"""
Docker container engine: DockerEngine implements the ContainerEngine port via the docker CLI.
"""

import os

from ..domain.container import ContainerEngine, ContainerEngineUnavailableError
from ..domain.process import ProcessError, ProcessHandle, ProcessRunner
from .process import CapturedOutputRunner

_BIN = "docker"


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
