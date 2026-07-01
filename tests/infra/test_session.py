"""
Tests for adda_dev.infra.session: FsSessionRepository.
"""

from pathlib import Path

import pytest

from adda_dev.infra.session import FsSessionRepository

# ---------------------------------------------------------------------------
# FsSessionRepository.create — directory creation
# ---------------------------------------------------------------------------


def test_fssessionrepository_create_creates_runtime_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    repo = FsSessionRepository()
    session = repo.create("demo")
    assert session.runtime_dir.is_dir()


def test_fssessionrepository_create_sets_dir_mode_0o700(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    repo = FsSessionRepository()
    session = repo.create("demo")
    mode = session.runtime_dir.stat().st_mode & 0o777
    assert mode == 0o700


def test_fssessionrepository_create_writes_session_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    repo = FsSessionRepository()
    session = repo.create("demo")
    assert (session.runtime_dir / "session.toml").is_file()


# ---------------------------------------------------------------------------
# FsSessionRepository.create — returned Session fields
# ---------------------------------------------------------------------------


def test_fssessionrepository_create_session_id_has_session_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    repo = FsSessionRepository()
    session = repo.create("demo")
    assert session.session_id.startswith("session-")


def test_fssessionrepository_create_started_at_is_utc_aware(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    repo = FsSessionRepository()
    session = repo.create("demo")
    assert session.started_at.tzinfo is not None
    assert session.started_at.utcoffset().total_seconds() == 0  # type: ignore[union-attr]


def test_fssessionrepository_create_sets_project_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    repo = FsSessionRepository()
    session = repo.create("my-project")
    assert session.project_name == "my-project"


def test_fssessionrepository_create_sets_issue_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    repo = FsSessionRepository()
    session = repo.create("demo", issue_id=99)
    assert session.issue_id == 99


def test_fssessionrepository_create_sets_runtime_dir_under_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    repo = FsSessionRepository()
    session = repo.create("demo")
    assert session.runtime_dir.parent == tmp_path / "adda-dev"


# ---------------------------------------------------------------------------
# FsSessionRepository.create — session.toml content
# ---------------------------------------------------------------------------


def test_fssessionrepository_create_none_issue_id_omitted_from_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    repo = FsSessionRepository()
    session = repo.create("demo", issue_id=None)
    content = (session.runtime_dir / "session.toml").read_text()
    assert "issue_id" not in content


# ---------------------------------------------------------------------------
# FsSessionRepository.delete
# ---------------------------------------------------------------------------


def test_fssessionrepository_delete_removes_runtime_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    repo = FsSessionRepository()
    session = repo.create("demo")
    assert session.runtime_dir.exists()
    repo.delete(session)
    assert not session.runtime_dir.exists()


def test_fssessionrepository_delete_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    repo = FsSessionRepository()
    session = repo.create("demo")
    repo.delete(session)
    # Second call must not raise
    repo.delete(session)
