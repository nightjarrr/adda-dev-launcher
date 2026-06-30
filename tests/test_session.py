"""
Tests for adda_dev.domain.session: Session entity.
"""

import dataclasses
from datetime import UTC, datetime
from pathlib import Path

import pytest

from adda_dev.domain.session import Session

_STARTED_AT = datetime(2026, 1, 1, tzinfo=UTC)
_RUNTIME_DIR = Path("/tmp/adda-dev/session-test-0001")


# ---------------------------------------------------------------------------
# Session — construction
# ---------------------------------------------------------------------------


def test_session_construction_sets_all_fields() -> None:
    session = Session(
        session_id="session-abc",
        project_name="demo",
        started_at=_STARTED_AT,
        runtime_dir=_RUNTIME_DIR,
        issue_id=42,
    )
    assert session.session_id == "session-abc"
    assert session.project_name == "demo"
    assert session.started_at == _STARTED_AT
    assert session.runtime_dir == _RUNTIME_DIR
    assert session.issue_id == 42


def test_session_issue_id_defaults_to_none() -> None:
    session = Session(
        session_id="session-abc",
        project_name="demo",
        started_at=_STARTED_AT,
        runtime_dir=_RUNTIME_DIR,
    )
    assert session.issue_id is None


# ---------------------------------------------------------------------------
# Session — frozen dataclass rejects mutation
# ---------------------------------------------------------------------------


def test_session_frozen_rejects_attribute_mutation() -> None:
    session = Session(
        session_id="session-abc",
        project_name="demo",
        started_at=_STARTED_AT,
        runtime_dir=_RUNTIME_DIR,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        session.session_id = "new-id"  # type: ignore[misc]
