"""
Tests for adda_dev.infra.container: DockerEngine and create_engine().
"""

import os
import stat
from pathlib import Path

import pytest

from adda_dev.common import AddaDevError
from adda_dev.infra.config import ContainerEngineChoice
from adda_dev.infra.container import ContainerEngine, ContainerEngineUnavailableError, DockerEngine, create_engine
from adda_dev.infra.process import ProcessHandle, ProcessRunner
from tests.conftest import FakeOutput

# ---------------------------------------------------------------------------
# Fake docker binary fixture helpers
# ---------------------------------------------------------------------------


def _write_fake_docker(bin_dir: Path, info_line: str, exit_code: int = 0) -> Path:
    """Write a minimal fake docker script to bin_dir/docker and make it executable."""
    docker_path = bin_dir / "docker"
    script = f"""#!/bin/sh
case "$1" in
  info) echo "{info_line}"; exit {exit_code} ;;
  pull) echo "pulled $2" ;;
  run)  printf "ARGV: %s\\n" "$*" ;;
  stop) echo "stopped $2" ;;
  exec) echo "exec $*" ;;
  logs) echo "logs $2" ;;
  inspect) echo "inspect $2" ;;
esac
exit 0
"""
    docker_path.write_text(script)
    docker_path.chmod(docker_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return docker_path


@pytest.fixture()
def rootless_docker_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fake docker binary that reports rootless mode; prepended to PATH."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_docker(bin_dir, "27.1.1||[name=seccomp,profile=builtin name=rootless name=cgroupns]")
    monkeypatch.setenv("PATH", str(bin_dir) + ":" + os.environ.get("PATH", ""))
    return bin_dir


@pytest.fixture()
def rootful_docker_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fake docker binary that reports root (non-rootless) mode; prepended to PATH."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_docker(bin_dir, "27.1.1||[name=seccomp,profile=builtin name=cgroupns]")
    monkeypatch.setenv("PATH", str(bin_dir) + ":" + os.environ.get("PATH", ""))
    return bin_dir


# ---------------------------------------------------------------------------
# DockerEngine — constructor / preflight
# ---------------------------------------------------------------------------


def test_dockerengine_rootless_preflight_parses_version(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    assert engine.version == "27.1.1"


def test_dockerengine_rootless_preflight_sets_rootless_true(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    assert engine.rootless is True


def test_dockerengine_rootful_preflight_sets_rootless_false(rootful_docker_path: Path) -> None:
    engine = DockerEngine()
    assert engine.rootless is False


def test_dockerengine_name_is_docker(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    assert engine.name == "docker"


def test_dockerengine_missing_binary_raises_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty_dir = tmp_path / "emptybin"
    empty_dir.mkdir()
    monkeypatch.setenv("PATH", str(empty_dir))
    with pytest.raises(ContainerEngineUnavailableError):
        DockerEngine()


def test_dockerengine_nonzero_info_exit_raises_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_docker(bin_dir, "daemon not running", exit_code=1)
    monkeypatch.setenv("PATH", str(bin_dir) + ":" + os.environ.get("PATH", ""))
    with pytest.raises(ContainerEngineUnavailableError):
        DockerEngine()


# ---------------------------------------------------------------------------
# Recording fake ProcessRunner for lifecycle method tests
# ---------------------------------------------------------------------------


class _RecordingHandle(ProcessHandle):
    def wait(self) -> int:
        return 0

    def terminate(self) -> None:
        pass

    def stdout(self) -> str:
        return ""

    def stderr(self) -> str:
        return ""


class _RecordingRunner(ProcessRunner):
    """Records every run() call; returns a trivial handle."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, str] | None]] = []
        self._handle = _RecordingHandle()

    def run(self, cmd: list[str], env: dict[str, str] | None = None) -> ProcessHandle:
        self.calls.append((cmd, env))
        return self._handle

    @property
    def last_cmd(self) -> list[str]:
        return self.calls[-1][0]

    @property
    def last_env(self) -> dict[str, str] | None:
        return self.calls[-1][1]

    @property
    def last_handle(self) -> ProcessHandle:
        return self._handle


# ---------------------------------------------------------------------------
# DockerEngine lifecycle methods — argv assertions
# ---------------------------------------------------------------------------


def test_dockerengine_pull_argv(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    handle = engine.pull(rec, "alpine")
    assert rec.last_cmd == ["docker", "pull", "alpine"]
    assert handle is rec.last_handle


def test_dockerengine_run_it_argv_basic(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    engine.run_it(rec, "alpine", "my-container", ["--flag", "val"], {})
    assert rec.last_cmd == ["docker", "run", "-it", "--name", "my-container", "--flag", "val", "alpine"]


def test_dockerengine_run_it_argv_with_remove(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    engine.run_it(rec, "alpine", "my-container", [], {}, remove=True)
    assert "--rm" in rec.last_cmd
    assert rec.last_cmd.index("--rm") < rec.last_cmd.index("--name")


def test_dockerengine_run_it_argv_without_remove_no_rm_flag(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    engine.run_it(rec, "alpine", "my-container", [], {}, remove=False)
    assert "--rm" not in rec.last_cmd


def test_dockerengine_run_it_argv_with_cmd(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    engine.run_it(rec, "alpine", "my-container", [], {}, cmd=["/bin/sh", "-c", "echo hi"])
    assert rec.last_cmd[-3:] == ["/bin/sh", "-c", "echo hi"]


def test_dockerengine_run_it_forwards_env(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    env = {"MY_VAR": "value", "TOKEN": "secret"}
    engine.run_it(rec, "alpine", "my-container", [], env)
    # provided keys must be present with their values; host PATH must also be present (overlay)
    assert rec.last_env is not None
    assert rec.last_env["MY_VAR"] == "value"
    assert rec.last_env["TOKEN"] == "secret"
    assert "PATH" in rec.last_env


def test_dockerengine_run_it_env_precedence_over_host(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    env = {"PATH": "/custom/bin"}
    engine.run_it(rec, "alpine", "my-container", [], env)
    assert rec.last_env is not None
    assert rec.last_env["PATH"] == "/custom/bin"


def test_dockerengine_run_it_env_defaults_to_none(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    engine.run_it(rec, "alpine", "my-container", [])
    assert rec.last_env is None


def test_dockerengine_run_d_argv_basic(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    engine.run_d(rec, "alpine", "my-container", ["--extra"], {})
    assert rec.last_cmd == ["docker", "run", "-d", "--name", "my-container", "--extra", "alpine"]


def test_dockerengine_run_d_argv_with_remove(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    engine.run_d(rec, "alpine", "my-container", [], {}, remove=True)
    assert "--rm" in rec.last_cmd


def test_dockerengine_run_d_forwards_env(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    env = {"SOME_VAR": "123"}
    engine.run_d(rec, "alpine", "my-container", [], env)
    # provided keys must be present; host PATH must also be present (overlay)
    assert rec.last_env is not None
    assert rec.last_env["SOME_VAR"] == "123"
    assert "PATH" in rec.last_env


def test_dockerengine_run_d_env_defaults_to_none(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    engine.run_d(rec, "alpine", "my-container", [])
    assert rec.last_env is None


def test_dockerengine_stop_argv(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    engine.stop(rec, "my-container")
    assert rec.last_cmd == ["docker", "stop", "my-container"]


def test_dockerengine_exec_argv(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    engine.exec(rec, "my-container", ["ls", "-la"])
    assert rec.last_cmd == ["docker", "exec", "my-container", "ls", "-la"]


def test_dockerengine_exec_it_argv(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    engine.exec_it(rec, "my-container", ["/bin/sh"])
    assert rec.last_cmd == ["docker", "exec", "-it", "my-container", "/bin/sh"]


def test_dockerengine_logs_f_argv(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    engine.logs_f(rec, "my-container")
    assert rec.last_cmd == ["docker", "logs", "-f", "my-container"]


def test_dockerengine_inspect_argv(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    engine.inspect(rec, "my-container")
    assert rec.last_cmd == ["docker", "inspect", "my-container"]


def test_dockerengine_methods_return_runner_handle(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    assert engine.pull(rec, "img") is rec.last_handle
    assert engine.stop(rec, "c") is rec.last_handle
    assert engine.exec(rec, "c", ["ls"]) is rec.last_handle
    assert engine.exec_it(rec, "c", ["sh"]) is rec.last_handle
    assert engine.logs_f(rec, "c") is rec.last_handle
    assert engine.inspect(rec, "c") is rec.last_handle
    assert engine.rm(rec, "c") is rec.last_handle
    assert engine.logs(rec, "c") is rec.last_handle


def test_dockerengine_rm_argv_without_force(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    engine.rm(rec, "my-container")
    assert rec.last_cmd == ["docker", "rm", "my-container"]


def test_dockerengine_rm_argv_with_force(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    engine.rm(rec, "my-container", force=True)
    assert rec.last_cmd == ["docker", "rm", "-f", "my-container"]


def test_dockerengine_rm_without_force_no_f_flag(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    engine.rm(rec, "my-container", force=False)
    assert "-f" not in rec.last_cmd


def test_dockerengine_logs_argv(rootless_docker_path: Path) -> None:
    engine = DockerEngine()
    rec = _RecordingRunner()
    engine.logs(rec, "my-container")
    assert rec.last_cmd == ["docker", "logs", "my-container"]


# ---------------------------------------------------------------------------
# create_engine — factory behaviour
# ---------------------------------------------------------------------------


def test_create_engine_docker_returns_container_engine(rootless_docker_path: Path) -> None:
    output = FakeOutput()
    engine = create_engine(ContainerEngineChoice.docker, output)
    assert isinstance(engine, ContainerEngine)


def test_create_engine_docker_emits_banner_with_name_and_version(rootless_docker_path: Path) -> None:
    output = FakeOutput()
    create_engine(ContainerEngineChoice.docker, output)
    assert any("docker" in msg and "27.1.1" in msg for msg in output.info_calls)


def test_create_engine_rootless_docker_banner_contains_rootless(rootless_docker_path: Path) -> None:
    output = FakeOutput()
    create_engine(ContainerEngineChoice.docker, output)
    assert any("rootless" in msg for msg in output.info_calls)


def test_create_engine_rootless_docker_emits_no_warning(rootless_docker_path: Path) -> None:
    output = FakeOutput()
    create_engine(ContainerEngineChoice.docker, output)
    assert len(output.warning_calls) == 0


def test_create_engine_rootful_docker_emits_one_warning(rootful_docker_path: Path) -> None:
    output = FakeOutput()
    create_engine(ContainerEngineChoice.docker, output)
    assert len(output.warning_calls) == 1


def test_create_engine_rootful_docker_warning_mentions_rootless(rootful_docker_path: Path) -> None:
    output = FakeOutput()
    create_engine(ContainerEngineChoice.docker, output)
    assert "rootless" in output.warning_calls[0]


def test_create_engine_podman_raises_adda_dev_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = FakeOutput()
    with pytest.raises(AddaDevError, match="not supported"):
        create_engine(ContainerEngineChoice.podman, output)
