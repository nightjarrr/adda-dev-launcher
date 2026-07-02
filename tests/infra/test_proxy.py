"""
Tests for adda_dev.infra.proxy: render_envoy_config and EnvoySidecar.
"""

import json
import socket
import stat
from pathlib import Path

import pytest

from adda_dev.domain.proxy import ProxyError
from adda_dev.infra.proxy import (
    ENVOY_SOCKET_CONTAINER_PATH,
    EnvoySidecar,
    render_envoy_config,
)
from tests.conftest import FakeContainerEngine, FakeOutput

_FAKE_ENVOY_IMAGE = "envoyproxy/envoy:test"


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeHandle:
    def __init__(self, rc: int = 0, out: str = "", err: str = "") -> None:
        self._rc = rc
        self._out = out
        self._err = err

    def wait(self) -> int:
        return self._rc

    def stdout(self) -> str:
        return self._out

    def stderr(self) -> str:
        return self._err

    def terminate(self) -> None:
        pass


class _FakeRunner:
    def run(self, cmd: list[str], env: dict[str, str] | None = None) -> _FakeHandle:
        return _FakeHandle()


class _ExitedEngine(FakeContainerEngine):
    """Engine that reports the container as not running on inspect."""

    def inspect(self, runner: object, name: str) -> _FakeHandle:  # type: ignore[override]
        self.calls.append(("inspect", name))
        state = [{"State": {"Running": False}}]
        return _FakeHandle(rc=0, out=json.dumps(state))

    def logs(self, runner: object, name: str) -> _FakeHandle:  # type: ignore[override]
        self.calls.append(("logs", name))
        return _FakeHandle(rc=0, out="envoy crashed", err="")


class _FailInspectEngine(FakeContainerEngine):
    """Engine that returns non-zero exit on inspect (container not found)."""

    def inspect(self, runner: object, name: str) -> _FakeHandle:  # type: ignore[override]
        self.calls.append(("inspect", name))
        return _FakeHandle(rc=1, out="", err="No such container")

    def logs(self, runner: object, name: str) -> _FakeHandle:  # type: ignore[override]
        self.calls.append(("logs", name))
        return _FakeHandle(rc=0, out="no container", err="")


class _AlwaysRunningEngine(FakeContainerEngine):
    """Engine that always reports the container as running but never creates the socket."""

    def inspect(self, runner: object, name: str) -> _FakeHandle:  # type: ignore[override]
        self.calls.append(("inspect", name))
        state = [{"State": {"Running": True}}]
        return _FakeHandle(rc=0, out=json.dumps(state))

    def logs(self, runner: object, name: str) -> _FakeHandle:  # type: ignore[override]
        self.calls.append(("logs", name))
        return _FakeHandle(rc=0, out="still starting", err="")


def _make_exited_sidecar() -> tuple[EnvoySidecar, _ExitedEngine]:
    """Sidecar backed by an engine that always reports exited; fails fast in polling."""
    eng = _ExitedEngine()
    sidecar = EnvoySidecar(eng, _FakeRunner(), _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=3)
    return sidecar, eng


def _bind_unix_socket(path: Path) -> socket.socket:
    """Bind a real AF_UNIX socket at path so is_socket() returns True."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(str(path))
    return sock


# ---------------------------------------------------------------------------
# render_envoy_config — real bundled template
# ---------------------------------------------------------------------------


def test_render_envoy_config_placeholder_gone() -> None:
    result = render_envoy_config(ENVOY_SOCKET_CONTAINER_PATH)
    assert "__ENVOY_SOCKET_PATH__" not in result


def test_render_envoy_config_socket_path_present() -> None:
    result = render_envoy_config(ENVOY_SOCKET_CONTAINER_PATH)
    assert ENVOY_SOCKET_CONTAINER_PATH in result


def test_render_envoy_config_custom_path() -> None:
    result = render_envoy_config("/custom/path/proxy.sock")
    assert "/custom/path/proxy.sock" in result
    assert "__ENVOY_SOCKET_PATH__" not in result


def test_render_envoy_config_returns_str() -> None:
    result = render_envoy_config(ENVOY_SOCKET_CONTAINER_PATH)
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# EnvoySidecar.start — filesystem setup
# (Use _ExitedEngine so polling terminates quickly after setup is complete.)
# ---------------------------------------------------------------------------


def test_envoy_sidecar_start_creates_proxy_socket_dir(tmp_path: Path) -> None:
    sidecar, _ = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(tmp_path)
    assert (tmp_path / "proxy_socket").is_dir()


def test_envoy_sidecar_start_creates_envoy_yaml(tmp_path: Path) -> None:
    sidecar, _ = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(tmp_path)
    config_path = tmp_path / "envoy.yaml"
    assert config_path.exists()
    assert ENVOY_SOCKET_CONTAINER_PATH in config_path.read_text()


def test_envoy_sidecar_start_config_permissions(tmp_path: Path) -> None:
    sidecar, _ = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(tmp_path)
    config_path = tmp_path / "envoy.yaml"
    assert config_path.exists()
    mode = stat.S_IMODE(config_path.stat().st_mode)
    assert mode == 0o600


def test_envoy_sidecar_start_proxy_socket_dir_permissions(tmp_path: Path) -> None:
    sidecar, _ = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(tmp_path)
    socket_dir = tmp_path / "proxy_socket"
    assert socket_dir.is_dir()
    mode = stat.S_IMODE(socket_dir.stat().st_mode)
    assert mode == 0o700


# ---------------------------------------------------------------------------
# EnvoySidecar.start — run_d args
# ---------------------------------------------------------------------------


def test_envoy_sidecar_start_calls_pull(tmp_path: Path) -> None:
    sidecar, engine = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(tmp_path)
    pull_calls = [c for c in engine.calls if c[0] == "pull"]
    assert any(_FAKE_ENVOY_IMAGE in str(c[1]) for c in pull_calls)


def test_envoy_sidecar_start_calls_run_d(tmp_path: Path) -> None:
    sidecar, engine = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(tmp_path)
    run_d_calls = [c for c in engine.calls if c[0] == "run_d"]
    assert len(run_d_calls) == 1


def test_envoy_sidecar_start_run_d_uses_envoy_image(tmp_path: Path) -> None:
    sidecar, engine = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(tmp_path)
    run_d_calls = [c for c in engine.calls if c[0] == "run_d"]
    _, (image, _name, _args, _env, _cmd, _remove) = run_d_calls[0]
    assert image == _FAKE_ENVOY_IMAGE


def test_envoy_sidecar_start_run_d_without_remove(tmp_path: Path) -> None:
    """Envoy container must start without --rm so logs survive after exit."""
    sidecar, engine = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(tmp_path)
    run_d_calls = [c for c in engine.calls if c[0] == "run_d"]
    _, (_image, _name, _args, _env, _cmd, remove) = run_d_calls[0]
    assert remove is False


def test_envoy_sidecar_start_run_d_cmd_uses_config_path(tmp_path: Path) -> None:
    sidecar, engine = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(tmp_path)
    run_d_calls = [c for c in engine.calls if c[0] == "run_d"]
    _, (_image, _name, _args, _env, cmd, _remove) = run_d_calls[0]
    assert cmd == ["-c", "/etc/adda-dev/envoy.yaml"]


def test_envoy_sidecar_start_run_d_args_include_cap_drop(tmp_path: Path) -> None:
    sidecar, engine = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(tmp_path)
    run_d_calls = [c for c in engine.calls if c[0] == "run_d"]
    _, (_image, _name, args, _env, _cmd, _remove) = run_d_calls[0]
    assert "--cap-drop" in args and "ALL" in args


def test_envoy_sidecar_start_run_d_args_include_read_only(tmp_path: Path) -> None:
    sidecar, engine = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(tmp_path)
    run_d_calls = [c for c in engine.calls if c[0] == "run_d"]
    _, (_image, _name, args, _env, _cmd, _remove) = run_d_calls[0]
    assert "--read-only" in args


def test_envoy_sidecar_start_run_d_args_include_config_mount(tmp_path: Path) -> None:
    sidecar, engine = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(tmp_path)
    run_d_calls = [c for c in engine.calls if c[0] == "run_d"]
    _, (_image, _name, args, _env, _cmd, _remove) = run_d_calls[0]
    mount_vals = [args[i + 1] for i, a in enumerate(args) if a == "--mount"]
    assert any("/etc/adda-dev/envoy.yaml" in m and "readonly" in m for m in mount_vals)


def test_envoy_sidecar_start_run_d_args_include_socket_dir_mount(tmp_path: Path) -> None:
    sidecar, engine = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(tmp_path)
    run_d_calls = [c for c in engine.calls if c[0] == "run_d"]
    _, (_image, _name, args, _env, _cmd, _remove) = run_d_calls[0]
    mount_vals = [args[i + 1] for i, a in enumerate(args) if a == "--mount"]
    assert any("/run/adda-dev-proxy" in m for m in mount_vals)


# ---------------------------------------------------------------------------
# EnvoySidecar.start — poll success (real AF_UNIX socket)
# ---------------------------------------------------------------------------


def test_envoy_sidecar_start_poll_success_returns_host_socket(tmp_path: Path) -> None:
    # Use an engine that binds the Unix socket as a side-effect of run_d, so is_socket() fires
    # on the very first poll iteration. FakeContainerEngine.inspect returns "" stdout which
    # causes json.loads to raise, triggering the except-branch (exited=True), so we override
    # inspect to report Running=True to force the poll to reach is_socket().
    socket_path = tmp_path / "proxy_socket" / "proxy.sock"

    class _SocketCreatingEngine(FakeContainerEngine):
        def run_d(  # type: ignore[override]
            self,
            runner: object,
            image: str,
            name: str,
            args: list[str],
            env: dict[str, str] | None = None,
            cmd: list[str] | None = None,
            remove: bool = False,
        ) -> _FakeHandle:
            self.calls.append(("run_d", (image, name, args, env, cmd, remove)))
            _bind_unix_socket(socket_path)
            return _FakeHandle(rc=0)

        def inspect(self, runner: object, name: str) -> _FakeHandle:  # type: ignore[override]
            self.calls.append(("inspect", name))
            state = [{"State": {"Running": True}}]
            return _FakeHandle(rc=0, out=json.dumps(state))

    eng = _SocketCreatingEngine()
    sidecar = EnvoySidecar(eng, _FakeRunner(), _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=5)
    result = sidecar.start(tmp_path)
    assert result == socket_path


def test_envoy_sidecar_start_poll_success_emits_ready_message(tmp_path: Path) -> None:
    socket_path = tmp_path / "proxy_socket" / "proxy.sock"

    class _SocketCreatingEngine(FakeContainerEngine):
        def run_d(  # type: ignore[override]
            self,
            runner: object,
            image: str,
            name: str,
            args: list[str],
            env: dict[str, str] | None = None,
            cmd: list[str] | None = None,
            remove: bool = False,
        ) -> _FakeHandle:
            self.calls.append(("run_d", (image, name, args, env, cmd, remove)))
            _bind_unix_socket(socket_path)
            return _FakeHandle(rc=0)

        def inspect(self, runner: object, name: str) -> _FakeHandle:  # type: ignore[override]
            self.calls.append(("inspect", name))
            state = [{"State": {"Running": True}}]
            return _FakeHandle(rc=0, out=json.dumps(state))

    output = FakeOutput()
    eng = _SocketCreatingEngine()
    sidecar = EnvoySidecar(eng, _FakeRunner(), _FAKE_ENVOY_IMAGE, output, sleep=lambda _: None, attempts=5)
    sidecar.start(tmp_path)
    assert any("ready" in msg.lower() or "envoy" in msg.lower() for msg in output.info_calls)


# ---------------------------------------------------------------------------
# EnvoySidecar.start — fail-fast on container exit
# ---------------------------------------------------------------------------


def test_envoy_sidecar_start_failfast_on_exit_raises_proxy_error(tmp_path: Path) -> None:
    eng = _ExitedEngine()
    sidecar = EnvoySidecar(eng, _FakeRunner(), _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=10)
    with pytest.raises(ProxyError, match="exited"):
        sidecar.start(tmp_path)


def test_envoy_sidecar_start_failfast_captures_logs(tmp_path: Path) -> None:
    eng = _ExitedEngine()
    sidecar = EnvoySidecar(eng, _FakeRunner(), _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=10)
    with pytest.raises(ProxyError) as exc_info:
        sidecar.start(tmp_path)
    assert "envoy crashed" in str(exc_info.value)


def test_envoy_sidecar_start_failfast_on_inspect_failure(tmp_path: Path) -> None:
    eng = _FailInspectEngine()
    sidecar = EnvoySidecar(eng, _FakeRunner(), _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=10)
    with pytest.raises(ProxyError):
        sidecar.start(tmp_path)


# ---------------------------------------------------------------------------
# EnvoySidecar.start — timeout
# ---------------------------------------------------------------------------


def test_envoy_sidecar_start_timeout_raises_proxy_error(tmp_path: Path) -> None:
    eng = _AlwaysRunningEngine()
    sidecar = EnvoySidecar(eng, _FakeRunner(), _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=3)
    with pytest.raises(ProxyError, match="not ready"):
        sidecar.start(tmp_path)


def test_envoy_sidecar_start_timeout_captures_logs(tmp_path: Path) -> None:
    eng = _AlwaysRunningEngine()
    sidecar = EnvoySidecar(eng, _FakeRunner(), _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=3)
    with pytest.raises(ProxyError) as exc_info:
        sidecar.start(tmp_path)
    assert "still starting" in str(exc_info.value)


# ---------------------------------------------------------------------------
# EnvoySidecar.start — run_d nonzero exit
# ---------------------------------------------------------------------------


def test_envoy_sidecar_start_run_d_nonzero_exit_raises(tmp_path: Path) -> None:
    """run_d returning non-zero must raise ProxyError before recording the name."""

    class _FailRunDEngine(FakeContainerEngine):
        def run_d(  # type: ignore[override]
            self,
            runner: object,
            image: str,
            name: str,
            args: list[str],
            env: dict[str, str] | None = None,
            cmd: list[str] | None = None,
            remove: bool = False,
        ) -> _FakeHandle:
            self.calls.append(("run_d", (image, name, args, env, cmd, remove)))
            return _FakeHandle(rc=1, out="", err="pull failed")

    eng = _FailRunDEngine()
    sidecar = EnvoySidecar(eng, _FakeRunner(), _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=3)
    with pytest.raises(ProxyError):
        sidecar.start(tmp_path)
    # stop() must be a no-op since _container_name was never set
    sidecar.stop()
    assert not any(c[0] in ("stop", "rm") for c in eng.calls)


# ---------------------------------------------------------------------------
# EnvoySidecar.stop
# ---------------------------------------------------------------------------


def test_envoy_sidecar_stop_before_start_is_noop() -> None:
    eng = FakeContainerEngine()
    sidecar = EnvoySidecar(eng, _FakeRunner(), _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=3)
    sidecar.stop()  # must not raise; no container name recorded
    assert not any(c[0] in ("stop", "rm") for c in eng.calls)


def test_envoy_sidecar_stop_after_start_calls_stop_and_rm(tmp_path: Path) -> None:
    socket_path = tmp_path / "proxy_socket" / "proxy.sock"

    class _SocketCreatingEngine(FakeContainerEngine):
        def run_d(  # type: ignore[override]
            self,
            runner: object,
            image: str,
            name: str,
            args: list[str],
            env: dict[str, str] | None = None,
            cmd: list[str] | None = None,
            remove: bool = False,
        ) -> _FakeHandle:
            self.calls.append(("run_d", (image, name, args, env, cmd, remove)))
            _bind_unix_socket(socket_path)
            return _FakeHandle(rc=0)

        def inspect(self, runner: object, name: str) -> _FakeHandle:  # type: ignore[override]
            self.calls.append(("inspect", name))
            state = [{"State": {"Running": True}}]
            return _FakeHandle(rc=0, out=json.dumps(state))

    eng = _SocketCreatingEngine()
    sidecar = EnvoySidecar(eng, _FakeRunner(), _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=5)
    sidecar.start(tmp_path)
    sidecar.stop()
    assert any(c[0] == "stop" for c in eng.calls)
    assert any(c[0] == "rm" for c in eng.calls)


def test_envoy_sidecar_stop_rm_uses_force(tmp_path: Path) -> None:
    socket_path = tmp_path / "proxy_socket" / "proxy.sock"

    class _SocketCreatingEngine(FakeContainerEngine):
        def run_d(  # type: ignore[override]
            self,
            runner: object,
            image: str,
            name: str,
            args: list[str],
            env: dict[str, str] | None = None,
            cmd: list[str] | None = None,
            remove: bool = False,
        ) -> _FakeHandle:
            self.calls.append(("run_d", (image, name, args, env, cmd, remove)))
            _bind_unix_socket(socket_path)
            return _FakeHandle(rc=0)

        def inspect(self, runner: object, name: str) -> _FakeHandle:  # type: ignore[override]
            self.calls.append(("inspect", name))
            state = [{"State": {"Running": True}}]
            return _FakeHandle(rc=0, out=json.dumps(state))

    eng = _SocketCreatingEngine()
    sidecar = EnvoySidecar(eng, _FakeRunner(), _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=5)
    sidecar.start(tmp_path)
    sidecar.stop()
    rm_calls = [c for c in eng.calls if c[0] == "rm"]
    assert rm_calls
    _, (name, force) = rm_calls[0]
    assert force is True
