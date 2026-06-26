"""
Tests for store.py: XDG resolution, file layout helpers, name validation, load_toml.
"""

from pathlib import Path

import pytest

from adda_dev.common import StrictModel
from adda_dev.store import (
    InvalidProjectNameError,
    SchemaValidationError,
    TomlParseError,
    app_config_file,
    load_toml,
    project_file,
    projects_dir,
    resolve_config_dir,
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
# File layout builders
# ---------------------------------------------------------------------------


def test_app_config_file_returns_correct_path(tmp_path: Path) -> None:
    assert app_config_file(tmp_path) == tmp_path / "config.toml"


def test_projects_dir_returns_correct_path(tmp_path: Path) -> None:
    assert projects_dir(tmp_path) == tmp_path / "projects"


def test_project_file_valid_name(tmp_path: Path) -> None:
    path = project_file(tmp_path, "my-project")
    assert path == tmp_path / "projects" / "my-project.toml"


# ---------------------------------------------------------------------------
# project_file name validation — accept cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "demo",
        "my-project",
        "org.repo",
        "repo_name",
        "UPPER",
        "a1b2",
        "a" * 64,
    ],
)
def test_project_file_valid_names(tmp_path: Path, name: str) -> None:
    path = project_file(tmp_path, name)
    assert path.name == f"{name}.toml"


# ---------------------------------------------------------------------------
# project_file name validation — reject cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "",
        ".",
        "..",
        "../escape",
        "a/b",
        "foo/bar",
        "name with spaces",
        "name\x00null",
        "name!bang",
        "/absolute",
    ],
)
def test_project_file_invalid_names(tmp_path: Path, name: str) -> None:
    with pytest.raises(InvalidProjectNameError):
        project_file(tmp_path, name)


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
