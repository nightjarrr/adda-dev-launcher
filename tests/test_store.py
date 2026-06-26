"""
Tests for store.py: XDG resolution, validate_file_name, load_toml.
"""

from pathlib import Path

import pytest

from adda_dev.common import StrictModel
from adda_dev.store import (
    InvalidFileNameError,
    SchemaValidationError,
    TomlParseError,
    load_toml,
    resolve_config_dir,
    validate_file_name,
)

# ---------------------------------------------------------------------------
# resolve_config_dir
# ---------------------------------------------------------------------------


def test_resolve_config_dir_uses_home_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    result = resolve_config_dir()
    assert result == Path.home() / ".config" / "adda-dev"


def test_resolve_config_dir_honours_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    result = resolve_config_dir()
    assert result == tmp_path / "adda-dev"


def test_resolve_config_dir_empty_xdg_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    result = resolve_config_dir()
    assert result == Path.home() / ".config" / "adda-dev"


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
