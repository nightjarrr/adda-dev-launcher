"""
Tests for store.py: XDG resolution, validate_file_name, load_toml, write_toml.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from adda_dev.common import StrictModel
from adda_dev.infra.store import (
    InvalidFileNameError,
    SchemaValidationError,
    StorageArea,
    TomlParseError,
    load_toml,
    resolve_storage_root,
    validate_file_name,
    write_toml,
)

# ---------------------------------------------------------------------------
# resolve_storage_root — config area
# ---------------------------------------------------------------------------


def test_resolve_storage_root_config_uses_home_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    result = resolve_storage_root(StorageArea.config)
    assert result == Path.home() / ".config" / "adda-dev"


def test_resolve_storage_root_config_honours_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    result = resolve_storage_root(StorageArea.config)
    assert result == tmp_path / "adda-dev"


def test_resolve_storage_root_config_empty_xdg_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    result = resolve_storage_root(StorageArea.config)
    assert result == Path.home() / ".config" / "adda-dev"


# ---------------------------------------------------------------------------
# resolve_storage_root — runtime area
# ---------------------------------------------------------------------------


def test_resolve_storage_root_runtime_uses_xdg_runtime_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    result = resolve_storage_root(StorageArea.runtime)
    assert result == tmp_path / "adda-dev"


def test_resolve_storage_root_runtime_falls_back_to_tmp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    result = resolve_storage_root(StorageArea.runtime)
    assert result == Path("/tmp") / "adda-dev"


def test_resolve_storage_root_runtime_empty_xdg_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", "")
    result = resolve_storage_root(StorageArea.runtime)
    assert result == Path("/tmp") / "adda-dev"


# ---------------------------------------------------------------------------
# resolve_storage_root — adda-dev segment is always appended
# ---------------------------------------------------------------------------


def test_resolve_storage_root_always_appends_adda_dev_segment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    result = resolve_storage_root(StorageArea.config)
    assert result.name == "adda-dev"
    assert result.parent == tmp_path


# ---------------------------------------------------------------------------
# validate_file_name — accept cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "demo",
        "my-project",
        "repo_name",
        "UPPER",
        "a1b2",
        "a_b-1",
        "a" * 64,
    ],
)
def test_validate_file_name_valid_names(name: str) -> None:
    assert validate_file_name(name) == name


# ---------------------------------------------------------------------------
# validate_file_name — reject cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "",
        ".",
        "..",
        "a.b",
        "../escape",
        "a/b",
        "foo/bar",
        "name with spaces",
        "name\x00null",
        "name!bang",
        "/absolute",
    ],
)
def test_validate_file_name_invalid_names(name: str) -> None:
    with pytest.raises(InvalidFileNameError):
        validate_file_name(name)


def test_validate_file_name_returns_name_unchanged() -> None:
    assert validate_file_name("my-project") == "my-project"


# ---------------------------------------------------------------------------
# load_toml — success path
# ---------------------------------------------------------------------------


class _SampleModel(StrictModel):
    x: int
    y: str


def test_load_toml_success(tmp_path: Path) -> None:
    toml_file = tmp_path / "sample.toml"
    toml_file.write_text('x = 1\ny = "hello"\n')
    result = load_toml(toml_file, _SampleModel)
    assert result.x == 1
    assert result.y == "hello"


# ---------------------------------------------------------------------------
# load_toml — parse error
# ---------------------------------------------------------------------------


def test_load_toml_parse_error_raises_toml_parse_error(tmp_path: Path) -> None:
    bad_toml = tmp_path / "bad.toml"
    bad_toml.write_text("x = [unclosed\n")
    with pytest.raises(TomlParseError):
        load_toml(bad_toml, _SampleModel)


# ---------------------------------------------------------------------------
# load_toml — schema validation error
# ---------------------------------------------------------------------------


def test_load_toml_schema_error_raises_schema_validation_error(tmp_path: Path) -> None:
    wrong_type = tmp_path / "wrong.toml"
    # x must be int; provide a string that is not coercible
    wrong_type.write_text('x = "not-an-int"\ny = "ok"\n')
    with pytest.raises(SchemaValidationError):
        load_toml(wrong_type, _SampleModel)


def test_load_toml_extra_key_raises_schema_validation_error(tmp_path: Path) -> None:
    extra_key = tmp_path / "extra.toml"
    extra_key.write_text('x = 1\ny = "ok"\nz = "extra"\n')
    with pytest.raises(SchemaValidationError):
        load_toml(extra_key, _SampleModel)


# ---------------------------------------------------------------------------
# write_toml — round-trip
# ---------------------------------------------------------------------------


class _RoundTripModel(StrictModel):
    name: str
    count: int
    label: str | None = None


def test_write_toml_round_trip(tmp_path: Path) -> None:
    model = _RoundTripModel(name="test", count=7)
    path = tmp_path / "out.toml"
    write_toml(path, model)
    loaded = load_toml(path, _RoundTripModel)
    assert loaded.name == "test"
    assert loaded.count == 7
    assert loaded.label is None


def test_write_toml_none_fields_omitted(tmp_path: Path) -> None:
    model = _RoundTripModel(name="test", count=1, label=None)
    path = tmp_path / "out.toml"
    write_toml(path, model)
    content = path.read_text()
    assert "label" not in content


# ---------------------------------------------------------------------------
# write_toml — datetime round-trip
# ---------------------------------------------------------------------------


class _DateModel(StrictModel):
    name: str
    started_at: datetime


def test_write_toml_datetime_round_trip(tmp_path: Path) -> None:
    ts = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
    model = _DateModel(name="demo", started_at=ts)
    path = tmp_path / "date.toml"
    write_toml(path, model)
    loaded = load_toml(path, _DateModel)
    assert loaded.started_at == ts
    assert loaded.started_at.tzinfo is not None
