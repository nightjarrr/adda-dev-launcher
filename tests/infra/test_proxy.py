"""
Tests for adda_dev.infra.proxy: render_envoy_config and EnvoySidecar.
"""

import json
import socket
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

from adda_dev.domain.proxy import ProxyError
from adda_dev.domain.session import Session
from adda_dev.infra.process import ProcessHandle, ProcessRunError
from adda_dev.infra.proxy import (
    ENVOY_SOCKET_CONTAINER_PATH,
    EnvoySidecar,
    render_envoy_config,
)
from tests.conftest import FakeContainerEngine, FakeOutput

_TEST_SESSION_ID = "adda-dev-session-test1234"


def _make_session(tmp_path: Path) -> Session:
    """Build a minimal Session whose runtime_dir is tmp_path."""
    return Session(
        session_id=_TEST_SESSION_ID,
        project_name="p",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        runtime_dir=tmp_path,
        issue_id=None,
    )


_FAKE_ENVOY_IMAGE = "envoyproxy/envoy:test"


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeHandle(ProcessHandle):
    def __init__(self, rc: int = 0, out: str = "", err: str = "") -> None:
        super().__init__([])
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
    sidecar = EnvoySidecar(eng, _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=3)
    return sidecar, eng


def _bind_unix_socket(path: Path) -> socket.socket:
    """Bind a real AF_UNIX socket at path so is_socket() returns True."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(str(path))
    return sock


# ---------------------------------------------------------------------------
# ProxyError — structured diagnostics and __str__ rendering
# ---------------------------------------------------------------------------


def test_proxyerror_str_includes_message() -> None:
    exc = ProxyError("msg", stdout="OUT", stderr="ERR")
    assert "msg" in str(exc)


def test_proxyerror_str_includes_stdout_section() -> None:
    exc = ProxyError("msg", stdout="OUT", stderr="ERR")
    assert "--- stdout ---" in str(exc)
    assert "OUT" in str(exc)


def test_proxyerror_str_includes_stderr_section() -> None:
    exc = ProxyError("msg", stdout="OUT", stderr="ERR")
    assert "--- stderr ---" in str(exc)
    assert "ERR" in str(exc)


def test_proxyerror_details_contains_stdout_and_stderr() -> None:
    exc = ProxyError("msg", stdout="OUT", stderr="ERR")
    detail_map = dict(exc.details)
    assert detail_map["stdout"] == "OUT"
    assert detail_map["stderr"] == "ERR"


def test_proxyerror_str_message_only_when_no_streams() -> None:
    exc = ProxyError("only message")
    assert str(exc) == "only message"
    assert "stdout" not in str(exc)
    assert "stderr" not in str(exc)


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
        sidecar.start(_make_session(tmp_path))
    assert (tmp_path / "proxy_socket").is_dir()


def test_envoy_sidecar_start_creates_envoy_yaml(tmp_path: Path) -> None:
    sidecar, _ = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(_make_session(tmp_path))
    config_path = tmp_path / "envoy.yaml"
    assert config_path.exists()
    assert ENVOY_SOCKET_CONTAINER_PATH in config_path.read_text()


def test_envoy_sidecar_start_config_permissions(tmp_path: Path) -> None:
    sidecar, _ = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(_make_session(tmp_path))
    config_path = tmp_path / "envoy.yaml"
    assert config_path.exists()
    mode = stat.S_IMODE(config_path.stat().st_mode)
    assert mode == 0o600


def test_envoy_sidecar_start_proxy_socket_dir_permissions(tmp_path: Path) -> None:
    sidecar, _ = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(_make_session(tmp_path))
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
        sidecar.start(_make_session(tmp_path))
    pull_calls = [c for c in engine.calls if c[0] == "pull"]
    assert any(_FAKE_ENVOY_IMAGE in str(c[1]) for c in pull_calls)


def test_envoy_sidecar_start_calls_run_d(tmp_path: Path) -> None:
    sidecar, engine = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(_make_session(tmp_path))
    run_d_calls = [c for c in engine.calls if c[0] == "run_d"]
    assert len(run_d_calls) == 1


def test_envoy_sidecar_start_run_d_uses_envoy_image(tmp_path: Path) -> None:
    sidecar, engine = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(_make_session(tmp_path))
    run_d_calls = [c for c in engine.calls if c[0] == "run_d"]
    _, (image, _name, _args, _env, _cmd, _remove) = run_d_calls[0]
    assert image == _FAKE_ENVOY_IMAGE


def test_envoy_sidecar_start_run_d_container_name_uses_session_id(tmp_path: Path) -> None:
    """Container name must be {session_id}-proxy — derived from the session, not the dir name."""
    sidecar, engine = _make_exited_sidecar()
    session = _make_session(tmp_path)
    with pytest.raises(ProxyError):
        sidecar.start(session)
    run_d_calls = [c for c in engine.calls if c[0] == "run_d"]
    _, (_image, name, _args, _env, _cmd, _remove) = run_d_calls[0]
    assert name == f"{session.session_id}-proxy"


def test_envoy_sidecar_start_run_d_without_remove(tmp_path: Path) -> None:
    """Envoy container must start without --rm so logs survive after exit."""
    sidecar, engine = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(_make_session(tmp_path))
    run_d_calls = [c for c in engine.calls if c[0] == "run_d"]
    _, (_image, _name, _args, _env, _cmd, remove) = run_d_calls[0]
    assert remove is False


def test_envoy_sidecar_start_run_d_cmd_uses_config_path(tmp_path: Path) -> None:
    sidecar, engine = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(_make_session(tmp_path))
    run_d_calls = [c for c in engine.calls if c[0] == "run_d"]
    _, (_image, _name, _args, _env, cmd, _remove) = run_d_calls[0]
    assert cmd == ["-c", "/etc/adda-dev/envoy.yaml"]


def test_envoy_sidecar_start_run_d_args_include_cap_drop(tmp_path: Path) -> None:
    sidecar, engine = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(_make_session(tmp_path))
    run_d_calls = [c for c in engine.calls if c[0] == "run_d"]
    _, (_image, _name, args, _env, _cmd, _remove) = run_d_calls[0]
    assert "--cap-drop" in args and "ALL" in args


def test_envoy_sidecar_start_run_d_args_include_read_only(tmp_path: Path) -> None:
    sidecar, engine = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(_make_session(tmp_path))
    run_d_calls = [c for c in engine.calls if c[0] == "run_d"]
    _, (_image, _name, args, _env, _cmd, _remove) = run_d_calls[0]
    assert "--read-only" in args


def test_envoy_sidecar_start_run_d_args_include_config_mount(tmp_path: Path) -> None:
    sidecar, engine = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(_make_session(tmp_path))
    run_d_calls = [c for c in engine.calls if c[0] == "run_d"]
    _, (_image, _name, args, _env, _cmd, _remove) = run_d_calls[0]
    mount_vals = [args[i + 1] for i, a in enumerate(args) if a == "--mount"]
    assert any("/etc/adda-dev/envoy.yaml" in m and "readonly" in m for m in mount_vals)


def test_envoy_sidecar_start_run_d_args_include_socket_dir_mount(tmp_path: Path) -> None:
    sidecar, engine = _make_exited_sidecar()
    with pytest.raises(ProxyError):
        sidecar.start(_make_session(tmp_path))
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
    sidecar = EnvoySidecar(eng, _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=5)
    result = sidecar.start(_make_session(tmp_path))
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
    sidecar = EnvoySidecar(eng, _FAKE_ENVOY_IMAGE, output, sleep=lambda _: None, attempts=5)
    sidecar.start(_make_session(tmp_path))
    assert any(label == "Proxy" for label, _ in output.step_calls)


# ---------------------------------------------------------------------------
# EnvoySidecar.start — fail-fast on container exit
# ---------------------------------------------------------------------------


def test_envoy_sidecar_start_failfast_on_exit_raises_proxy_error(tmp_path: Path) -> None:
    eng = _ExitedEngine()
    sidecar = EnvoySidecar(eng, _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=10)
    with pytest.raises(ProxyError, match="exited"):
        sidecar.start(_make_session(tmp_path))


def test_envoy_sidecar_start_failfast_captures_logs(tmp_path: Path) -> None:
    eng = _ExitedEngine()
    sidecar = EnvoySidecar(eng, _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=10)
    with pytest.raises(ProxyError) as exc_info:
        sidecar.start(_make_session(tmp_path))
    assert dict(exc_info.value.details).get("stdout") == "envoy crashed"


def test_envoy_sidecar_start_failfast_on_inspect_failure(tmp_path: Path) -> None:
    eng = _FailInspectEngine()
    sidecar = EnvoySidecar(eng, _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=10)
    with pytest.raises(ProxyError):
        sidecar.start(_make_session(tmp_path))


# ---------------------------------------------------------------------------
# EnvoySidecar.start — timeout
# ---------------------------------------------------------------------------


def test_envoy_sidecar_start_timeout_raises_proxy_error(tmp_path: Path) -> None:
    eng = _AlwaysRunningEngine()
    sidecar = EnvoySidecar(eng, _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=3)
    with pytest.raises(ProxyError, match="not ready"):
        sidecar.start(_make_session(tmp_path))


def test_envoy_sidecar_start_timeout_captures_logs(tmp_path: Path) -> None:
    eng = _AlwaysRunningEngine()
    sidecar = EnvoySidecar(eng, _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=3)
    with pytest.raises(ProxyError) as exc_info:
        sidecar.start(_make_session(tmp_path))
    assert dict(exc_info.value.details).get("stdout") == "still starting"


# ---------------------------------------------------------------------------
# EnvoySidecar.start — run_d nonzero exit
# ---------------------------------------------------------------------------


def test_envoy_sidecar_start_run_d_nonzero_exit_raises(tmp_path: Path) -> None:
    """run_d returning non-zero must raise ProcessRunError before recording the name."""

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
    sidecar = EnvoySidecar(eng, _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=3)
    with pytest.raises(ProcessRunError):
        sidecar.start(_make_session(tmp_path))
    # stop() must be a no-op since _container_name was never set
    sidecar.stop()
    assert not any(c[0] in ("stop", "rm") for c in eng.calls)


# ---------------------------------------------------------------------------
# EnvoySidecar.stop
# ---------------------------------------------------------------------------


def test_envoy_sidecar_stop_before_start_is_noop() -> None:
    eng = FakeContainerEngine()
    sidecar = EnvoySidecar(eng, _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=3)
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
    sidecar = EnvoySidecar(eng, _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=5)
    sidecar.start(_make_session(tmp_path))
    sidecar.stop()
    assert any(c[0] == "stop" for c in eng.calls)
    assert any(c[0] == "rm" for c in eng.calls)


# ---------------------------------------------------------------------------
# EnvoySidecar.stop — best-effort exception swallowing
# ---------------------------------------------------------------------------


class _RaisingStopEngine(FakeContainerEngine):
    """Engine whose stop() raises; rm() succeeds."""

    def stop(self, runner: object, name: str) -> _FakeHandle:  # type: ignore[override]
        raise RuntimeError("stop failed")


class _RaisingRmEngine(FakeContainerEngine):
    """Engine whose stop() succeeds but rm() raises."""

    def rm(self, runner: object, name: str, force: bool = False) -> _FakeHandle:  # type: ignore[override]
        raise RuntimeError("rm failed")


class _RaisingInspectEngine(FakeContainerEngine):
    """Engine whose inspect() raises; logs() returns a trivial handle."""

    def inspect(self, runner: object, name: str) -> _FakeHandle:  # type: ignore[override]
        raise RuntimeError("inspect failed")

    def logs(self, runner: object, name: str) -> _FakeHandle:  # type: ignore[override]
        return _FakeHandle(rc=0, out="", err="")


class _RaisingLogsEngine(_ExitedEngine):
    """Engine that reports the container as exited but raises on logs()."""

    def logs(self, runner: object, name: str) -> _FakeHandle:  # type: ignore[override]
        raise RuntimeError("logs failed")


def test_envoy_sidecar_stop_swallows_stop_exception() -> None:
    sidecar = EnvoySidecar(_RaisingStopEngine(), _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None)
    sidecar._container_name = "test-envoy"
    sidecar.stop()  # must not raise


def test_envoy_sidecar_stop_swallows_rm_exception() -> None:
    sidecar = EnvoySidecar(_RaisingRmEngine(), _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None)
    sidecar._container_name = "test-envoy"
    sidecar.stop()  # must not raise


def test_envoy_sidecar_container_exited_on_inspect_exception(tmp_path: Path) -> None:
    sidecar = EnvoySidecar(_RaisingInspectEngine(), _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=3)
    with pytest.raises(ProxyError):
        sidecar.start(_make_session(tmp_path))


def test_envoy_sidecar_capture_logs_swallows_exception(tmp_path: Path) -> None:
    sidecar = EnvoySidecar(_RaisingLogsEngine(), _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=3)
    with pytest.raises(ProxyError):
        sidecar.start(_make_session(tmp_path))


# ---------------------------------------------------------------------------
# EnvoySidecar.start — pull failure
# ---------------------------------------------------------------------------


class _FailingPullHandle(ProcessHandle):
    def __init__(self) -> None:
        super().__init__(["docker", "pull", "test-image"])

    def wait(self) -> int:
        return 1

    def stdout(self) -> str:
        return ""

    def stderr(self) -> str:
        return "manifest unknown"

    def terminate(self) -> None:
        pass


class _FailingPullEngine(FakeContainerEngine):
    """Engine whose pull() returns a handle with non-zero exit code."""

    def pull(self, runner: object, image: str) -> _FailingPullHandle:  # type: ignore[override]
        self.calls.append(("pull", image))
        return _FailingPullHandle()


def test_envoy_sidecar_start_raises_process_run_error_on_pull_failure(tmp_path: Path) -> None:
    eng = _FailingPullEngine()
    sidecar = EnvoySidecar(eng, _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=3)
    with pytest.raises(ProcessRunError) as exc_info:
        sidecar.start(_make_session(tmp_path))
    assert _FAKE_ENVOY_IMAGE in str(exc_info.value.args[0])


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
    sidecar = EnvoySidecar(eng, _FAKE_ENVOY_IMAGE, FakeOutput(), sleep=lambda _: None, attempts=5)
    sidecar.start(_make_session(tmp_path))
    sidecar.stop()
    rm_calls = [c for c in eng.calls if c[0] == "rm"]
    assert rm_calls
    _, (name, force) = rm_calls[0]
    assert force is True
