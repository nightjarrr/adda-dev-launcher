"""
Tests for adda_dev.infra.tmux: TmuxServer and TmuxSession.
"""

import os
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

from adda_dev.domain.session import Session
from adda_dev.infra.tmux import _BUNDLED_CONFIG, TMUX_SERVER_NAME, TmuxError, TmuxServer, TmuxSession

# ---------------------------------------------------------------------------
# Fake tmux binary fixture helpers
# ---------------------------------------------------------------------------


def _write_fake_tmux(bin_dir: Path, version_line: str = "tmux 3.4", version_exit: int = 0) -> Path:
    """Write a minimal fake tmux script to bin_dir/tmux that records its argv to a file."""
    tmux_path = bin_dir / "tmux"
    argv_file = bin_dir / "last_argv"
    script = f"""#!/bin/sh
printf '%s\\n' "$@" > "{argv_file}"
case "$1" in
  -V) echo "{version_line}"; exit {version_exit} ;;
  *) exit 0 ;;
esac
"""
    tmux_path.write_text(script)
    tmux_path.chmod(tmux_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return tmux_path


def _read_argv(bin_dir: Path) -> list[str]:
    """Read the argv file written by the fake tmux script."""
    argv_file = bin_dir / "last_argv"
    return argv_file.read_text().splitlines() if argv_file.exists() else []


def _make_session(session_id: str = "adda-dev-session-abc12345") -> Session:
    return Session(
        session_id=session_id,
        project_name="test-project",
        started_at=datetime.now(UTC),
        runtime_dir=Path("/tmp/test-session"),
    )


@pytest.fixture()
def fake_tmux_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fake tmux binary reporting version 3.4; prepended to PATH."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_tmux(bin_dir, "tmux 3.4")
    monkeypatch.setenv("PATH", str(bin_dir) + ":" + os.environ.get("PATH", ""))
    return bin_dir


@pytest.fixture()
def nonzero_tmux_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fake tmux binary that exits non-zero on -V."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_tmux(bin_dir, "error: daemon not running", version_exit=1)
    monkeypatch.setenv("PATH", str(bin_dir) + ":" + os.environ.get("PATH", ""))
    return bin_dir


# ---------------------------------------------------------------------------
# TmuxServer — constructor / preflight
# ---------------------------------------------------------------------------


def test_tmuxserver_missing_binary_raises_tmux_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty_dir = tmp_path / "emptybin"
    empty_dir.mkdir()
    monkeypatch.setenv("PATH", str(empty_dir))
    with pytest.raises(TmuxError, match="not found or not executable"):
        TmuxServer()


def test_tmuxserver_nonzero_version_exit_raises_tmux_error(nonzero_tmux_path: Path) -> None:
    with pytest.raises(TmuxError, match="not available"):
        TmuxServer()


def test_tmuxserver_version_property_parsed(fake_tmux_path: Path) -> None:
    server = TmuxServer()
    assert server.version == "3.4"


# ---------------------------------------------------------------------------
# TmuxServer — ensure_no_reentry
# ---------------------------------------------------------------------------


def test_tmuxserver_ensure_no_reentry_raises_when_inside_adda_dev_session(
    fake_tmux_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TMUX", f"/tmp/tmux-1000/{TMUX_SERVER_NAME},12345,0")
    server = TmuxServer()
    with pytest.raises(TmuxError, match="does not support running from inside"):
        server.ensure_no_reentry()


def test_tmuxserver_ensure_no_reentry_does_not_raise_when_tmux_unset(
    fake_tmux_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TMUX", raising=False)
    server = TmuxServer()
    server.ensure_no_reentry()  # must not raise


def test_tmuxserver_ensure_no_reentry_does_not_raise_for_different_server(
    fake_tmux_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,12345,0")
    server = TmuxServer()
    server.ensure_no_reentry()  # must not raise


# ---------------------------------------------------------------------------
# TmuxServer — new_session
# ---------------------------------------------------------------------------


def test_tmuxserver_new_session_includes_server_flag(fake_tmux_path: Path) -> None:
    server = TmuxServer()
    session = _make_session()
    server.new_session(session, "main", ["bash"])
    argv = _read_argv(fake_tmux_path)
    assert "-L" in argv
    assert TMUX_SERVER_NAME in argv
    assert argv[argv.index("-L") + 1] == TMUX_SERVER_NAME


def test_tmuxserver_new_session_includes_config_flag(fake_tmux_path: Path) -> None:
    server = TmuxServer()
    session = _make_session()
    server.new_session(session, "main", ["bash"])
    argv = _read_argv(fake_tmux_path)
    assert "-f" in argv
    assert str(_BUNDLED_CONFIG) in argv
    assert argv[argv.index("-f") + 1] == str(_BUNDLED_CONFIG)


def test_tmuxserver_new_session_includes_new_session_subcommand(fake_tmux_path: Path) -> None:
    server = TmuxServer()
    session = _make_session("adda-dev-session-abc12345")
    server.new_session(session, "main", ["bash"])
    argv = _read_argv(fake_tmux_path)
    assert "new-session" in argv
    assert "-d" in argv
    assert "-s" in argv
    assert "adda-dev-session-abc12345" in argv
    assert argv[argv.index("-s") + 1] == "adda-dev-session-abc12345"


def test_tmuxserver_new_session_includes_window_name(fake_tmux_path: Path) -> None:
    server = TmuxServer()
    session = _make_session()
    server.new_session(session, "my-window", ["bash"])
    argv = _read_argv(fake_tmux_path)
    assert "-n" in argv
    assert argv[argv.index("-n") + 1] == "my-window"


def test_tmuxserver_new_session_appends_cmd_args(fake_tmux_path: Path) -> None:
    server = TmuxServer()
    session = _make_session()
    server.new_session(session, "main", ["/bin/sh", "-c", "echo hi"])
    argv = _read_argv(fake_tmux_path)
    assert "/bin/sh" in argv
    assert "-c" in argv
    assert "echo hi" in argv


def test_tmuxserver_new_session_returns_tmux_session(fake_tmux_path: Path) -> None:
    server = TmuxServer()
    session = _make_session("adda-dev-session-abc12345")
    result = server.new_session(session, "main", ["bash"])
    assert isinstance(result, TmuxSession)
    assert result._session_name == "adda-dev-session-abc12345"


def test_tmuxserver_new_session_raises_on_nonzero_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tmux_path = bin_dir / "tmux"
    script = """#!/bin/sh
case "$1" in
  -V) echo "tmux 3.4"; exit 0 ;;
  *) echo "error: target not found" >&2; exit 1 ;;
esac
"""
    tmux_path.write_text(script)
    tmux_path.chmod(tmux_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", str(bin_dir) + ":" + os.environ.get("PATH", ""))
    server = TmuxServer()
    with pytest.raises(TmuxError, match="new-session failed"):
        server.new_session(_make_session(), "main", ["bash"])


def test_tmuxserver_new_session_uses_bundled_config(fake_tmux_path: Path) -> None:
    server = TmuxServer()
    session = _make_session()
    server.new_session(session, "main", ["bash"])
    argv = _read_argv(fake_tmux_path)
    assert str(_BUNDLED_CONFIG) in argv


# ---------------------------------------------------------------------------
# TmuxServer — kill_server
# ---------------------------------------------------------------------------


def test_tmuxserver_kill_server_invokes_kill_server_subcommand(fake_tmux_path: Path) -> None:
    server = TmuxServer()
    server.kill_server()
    argv = _read_argv(fake_tmux_path)
    assert "kill-server" in argv


def test_tmuxserver_kill_server_swallows_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tmux_path = bin_dir / "tmux"
    script = """#!/bin/sh
case "$1" in
  -V) echo "tmux 3.4"; exit 0 ;;
  *) exit 1 ;;
esac
"""
    tmux_path.write_text(script)
    tmux_path.chmod(tmux_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", str(bin_dir) + ":" + os.environ.get("PATH", ""))
    server = TmuxServer()
    server.kill_server()  # must not raise even on non-zero exit


# ---------------------------------------------------------------------------
# TmuxSession — new_window
# ---------------------------------------------------------------------------


def test_tmuxsession_new_window_includes_server_and_subcommand(fake_tmux_path: Path) -> None:
    server = TmuxServer()
    ts = server.new_session(_make_session("adda-dev-session-abc12345"), "main", ["bash"])
    ts.new_window("extra", ["bash"])
    argv = _read_argv(fake_tmux_path)
    assert "-L" in argv
    assert TMUX_SERVER_NAME in argv
    assert "new-window" in argv
    assert "-t" in argv
    assert "adda-dev-session-abc12345" in argv


def test_tmuxsession_new_window_includes_window_name(fake_tmux_path: Path) -> None:
    server = TmuxServer()
    ts = server.new_session(_make_session(), "main", ["bash"])
    ts.new_window("extra-window", ["bash"])
    argv = _read_argv(fake_tmux_path)
    assert "-n" in argv
    assert "extra-window" in argv


def test_tmuxsession_new_window_appends_cmd_args(fake_tmux_path: Path) -> None:
    server = TmuxServer()
    ts = server.new_session(_make_session(), "main", ["bash"])
    ts.new_window("extra", ["/bin/sh", "-c", "ls"])
    argv = _read_argv(fake_tmux_path)
    assert "/bin/sh" in argv
    assert "-c" in argv
    assert "ls" in argv


def test_tmuxsession_new_window_raises_on_nonzero_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tmux_path = bin_dir / "tmux"
    script = """#!/bin/sh
echo "error: session not found" >&2
exit 1
"""
    tmux_path.write_text(script)
    tmux_path.chmod(tmux_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", str(bin_dir) + ":" + os.environ.get("PATH", ""))
    ts = TmuxSession("adda-dev-session-abc12345")
    with pytest.raises(TmuxError, match="new-window failed"):
        ts.new_window("extra", ["bash"])


# ---------------------------------------------------------------------------
# TmuxSession — kill_window
# ---------------------------------------------------------------------------


def test_tmuxsession_kill_window_targets_session_colon_window(fake_tmux_path: Path) -> None:
    server = TmuxServer()
    ts = server.new_session(_make_session("adda-dev-session-abc12345"), "main", ["bash"])
    ts.kill_window("extra-window")
    argv = _read_argv(fake_tmux_path)
    assert "kill-window" in argv
    assert "adda-dev-session-abc12345:extra-window" in argv


def test_tmuxsession_kill_window_swallows_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tmux_path = bin_dir / "tmux"
    script = """#!/bin/sh
case "$1" in
  -V) echo "tmux 3.4"; exit 0 ;;
  *) exit 1 ;;
esac
"""
    tmux_path.write_text(script)
    tmux_path.chmod(tmux_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", str(bin_dir) + ":" + os.environ.get("PATH", ""))
    TmuxServer()
    ts = TmuxSession("adda-dev-session-abc12345")
    ts.kill_window("extra")  # must not raise


# ---------------------------------------------------------------------------
# TmuxSession — attach
# ---------------------------------------------------------------------------


def test_tmuxsession_attach_command_is_attach_session(fake_tmux_path: Path) -> None:
    server = TmuxServer()
    ts = server.new_session(_make_session("adda-dev-session-abc12345"), "main", ["bash"])
    ts.attach()
    argv = _read_argv(fake_tmux_path)
    assert "attach-session" in argv
    assert "-t" in argv
    assert "adda-dev-session-abc12345" in argv


def test_tmuxsession_attach_uses_default_runner(fake_tmux_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from adda_dev.infra import tmux as tmux_module
    from adda_dev.infra.process import DefaultRunner, ProcessHandle

    instantiated: list[bool] = []

    class _TrackingRunner(DefaultRunner):
        def __init__(self) -> None:
            instantiated.append(True)
            super().__init__()

        def run(self, cmd: list[str], env: dict[str, str] | None = None) -> ProcessHandle:
            return super().run(cmd, env)

    monkeypatch.setattr(tmux_module, "DefaultRunner", _TrackingRunner)
    server = TmuxServer()
    ts = server.new_session(_make_session(), "main", ["bash"])
    ts.attach()
    assert instantiated, "DefaultRunner was not instantiated during attach()"


# ---------------------------------------------------------------------------
# TmuxSession — kill
# ---------------------------------------------------------------------------


def test_tmuxsession_kill_command_is_kill_session(fake_tmux_path: Path) -> None:
    server = TmuxServer()
    ts = server.new_session(_make_session("adda-dev-session-abc12345"), "main", ["bash"])
    ts.kill()
    argv = _read_argv(fake_tmux_path)
    assert "kill-session" in argv
    assert "adda-dev-session-abc12345" in argv


def test_tmuxsession_kill_swallows_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tmux_path = bin_dir / "tmux"
    script = """#!/bin/sh
case "$1" in
  -V) echo "tmux 3.4"; exit 0 ;;
  *) exit 1 ;;
esac
"""
    tmux_path.write_text(script)
    tmux_path.chmod(tmux_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", str(bin_dir) + ":" + os.environ.get("PATH", ""))
    TmuxServer()
    ts = TmuxSession("adda-dev-session-abc12345")
    ts.kill()  # must not raise
