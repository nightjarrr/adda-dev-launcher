"""
Tests for project.py: ProjectFileModel validation, Project resolution, Project.load paths.
"""

from pathlib import Path

import pytest

from adda_dev.app_config import AppConfig, ProjectDefaults
from adda_dev.llm_backend import LlmBackend
from adda_dev.project import PROJECTS_DIR_NAME, Project, ProjectFileModel, ProjectNotFoundError
from adda_dev.store import InvalidFileNameError, SchemaValidationError, TomlParseError

DATA_DIR = Path(__file__).parent / "data" / "config"

# Shared defaults using built-in values.
_DEFAULTS = ProjectDefaults()

# Non-default defaults to exercise override resolution.
_CUSTOM_DEFAULTS = ProjectDefaults.model_validate({"tmpfs": {"home": "1g", "workspace": "512m", "tmp": "128m"}})


# ---------------------------------------------------------------------------
# ProjectFileModel — required fields
# ---------------------------------------------------------------------------


def _valid_file_data() -> dict[str, object]:
    return {
        "owner": "nightjarrr",
        "repo": "adda-dev-launcher",
        "image": "ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0",
        "github_keyring_key": "demo-token",
        "backend": "deepseek",
    }


def test_project_file_model_valid_minimal() -> None:
    pf = ProjectFileModel.model_validate(_valid_file_data())
    assert pf.owner == "nightjarrr"
    assert pf.backend == LlmBackend.deepseek
    assert pf.tmpfs is None


def test_project_file_model_valid_with_tmpfs() -> None:
    data = _valid_file_data()
    data["tmpfs"] = {"workspace": "2g"}
    pf = ProjectFileModel.model_validate(data)
    assert pf.tmpfs is not None
    assert pf.tmpfs.workspace == "2g"
    assert pf.tmpfs.home is None


def test_project_file_model_missing_owner_rejected() -> None:
    data = _valid_file_data()
    del data["owner"]
    with pytest.raises(Exception):
        ProjectFileModel.model_validate(data)


def test_project_file_model_missing_repo_rejected() -> None:
    data = _valid_file_data()
    del data["repo"]
    with pytest.raises(Exception):
        ProjectFileModel.model_validate(data)


def test_project_file_model_missing_backend_rejected() -> None:
    data = _valid_file_data()
    del data["backend"]
    with pytest.raises(Exception):
        ProjectFileModel.model_validate(data)


def test_project_file_model_missing_image_rejected() -> None:
    data = _valid_file_data()
    del data["image"]
    with pytest.raises(Exception):
        ProjectFileModel.model_validate(data)


def test_project_file_model_missing_github_keyring_key_rejected() -> None:
    data = _valid_file_data()
    del data["github_keyring_key"]
    with pytest.raises(Exception):
        ProjectFileModel.model_validate(data)


def test_project_file_model_unknown_key_rejected() -> None:
    data = _valid_file_data()
    data["unknown"] = "value"
    with pytest.raises(Exception):
        ProjectFileModel.model_validate(data)


def test_project_file_model_bad_owner_rejected() -> None:
    data = _valid_file_data()
    data["owner"] = "bad/owner"
    with pytest.raises(Exception):
        ProjectFileModel.model_validate(data)


def test_project_file_model_bad_repo_rejected() -> None:
    data = _valid_file_data()
    data["repo"] = "bad repo"
    with pytest.raises(Exception):
        ProjectFileModel.model_validate(data)


def test_project_file_model_invalid_backend_rejected() -> None:
    data = _valid_file_data()
    data["backend"] = "openai"
    with pytest.raises(Exception):
        ProjectFileModel.model_validate(data)


def test_project_file_model_owner_with_dot_accepted() -> None:
    # GitHub owner/repo may contain dots — unrelated to the registry slug constraint.
    data = _valid_file_data()
    data["repo"] = "my.repo"
    pf = ProjectFileModel.model_validate(data)
    assert pf.repo == "my.repo"


# ---------------------------------------------------------------------------
# Project._from_file — tmpfs resolution: no override → defaults pass through
# ---------------------------------------------------------------------------


def test_project_from_file_no_tmpfs_override_uses_defaults() -> None:
    pf = ProjectFileModel.model_validate(_valid_file_data())
    proj = Project._from_file("demo", pf, _CUSTOM_DEFAULTS)
    assert proj.tmpfs.home == "1g"
    assert proj.tmpfs.workspace == "512m"
    assert proj.tmpfs.tmp == "128m"


def test_project_from_file_no_tmpfs_override_uses_builtin_defaults() -> None:
    pf = ProjectFileModel.model_validate(_valid_file_data())
    proj = Project._from_file("demo", pf, _DEFAULTS)
    assert proj.tmpfs.home == "512m"
    assert proj.tmpfs.workspace == "256m"
    assert proj.tmpfs.tmp == "256m"


# ---------------------------------------------------------------------------
# Project._from_file — full tmpfs override
# ---------------------------------------------------------------------------


def test_project_from_file_full_tmpfs_override() -> None:
    data = _valid_file_data()
    data["tmpfs"] = {"home": "2g", "workspace": "1g", "tmp": "512m"}
    pf = ProjectFileModel.model_validate(data)
    proj = Project._from_file("demo", pf, _DEFAULTS)
    assert proj.tmpfs.home == "2g"
    assert proj.tmpfs.workspace == "1g"
    assert proj.tmpfs.tmp == "512m"


# ---------------------------------------------------------------------------
# Project._from_file — partial tmpfs override (field-wise merge)
# ---------------------------------------------------------------------------


def test_project_from_file_partial_tmpfs_override_workspace_only() -> None:
    data = _valid_file_data()
    data["tmpfs"] = {"workspace": "2g"}
    pf = ProjectFileModel.model_validate(data)
    proj = Project._from_file("demo", pf, _CUSTOM_DEFAULTS)
    # workspace overridden; home and tmp from custom defaults
    assert proj.tmpfs.workspace == "2g"
    assert proj.tmpfs.home == "1g"
    assert proj.tmpfs.tmp == "128m"


def test_project_from_file_partial_tmpfs_override_home_only() -> None:
    data = _valid_file_data()
    data["tmpfs"] = {"home": "4g"}
    pf = ProjectFileModel.model_validate(data)
    proj = Project._from_file("demo", pf, _DEFAULTS)
    assert proj.tmpfs.home == "4g"
    assert proj.tmpfs.workspace == "256m"
    assert proj.tmpfs.tmp == "256m"


# ---------------------------------------------------------------------------
# Project._from_file — identity fields pass through
# ---------------------------------------------------------------------------


def test_project_from_file_identity_fields() -> None:
    pf = ProjectFileModel.model_validate(_valid_file_data())
    proj = Project._from_file("myproj", pf, _DEFAULTS)
    assert proj.name == "myproj"
    assert proj.owner == "nightjarrr"
    assert proj.repo == "adda-dev-launcher"
    assert proj.image == "ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0"
    assert proj.github_keyring_key == "demo-token"
    assert proj.backend == LlmBackend.deepseek


# ---------------------------------------------------------------------------
# Project.load — valid project file
# ---------------------------------------------------------------------------


def test_project_load_valid(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    proj_file = tmp_path / "projects" / "demo.toml"
    proj_file.write_text(
        'owner = "nightjarrr"\n'
        'repo = "adda-dev-launcher"\n'
        'image = "ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0"\n'
        'github_keyring_key = "demo-token"\n'
        'backend = "anthropic"\n'
    )
    proj = Project.load("demo", _DEFAULTS, config_dir=tmp_path)
    assert proj.name == "demo"
    assert proj.backend == LlmBackend.anthropic
    assert proj.tmpfs.home == "512m"


def test_project_load_from_static_fixture() -> None:
    proj = Project.load("demo", _DEFAULTS, config_dir=DATA_DIR)
    assert proj.name == "demo"
    assert proj.backend == LlmBackend.deepseek
    assert proj.tmpfs.workspace == "2g"
    # home and tmp from built-in defaults
    assert proj.tmpfs.home == "512m"
    assert proj.tmpfs.tmp == "256m"


# ---------------------------------------------------------------------------
# Project.load — builds correct path (entity owns <name>.toml naming)
# ---------------------------------------------------------------------------


def test_project_load_builds_correct_path(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    proj_file = tmp_path / "projects" / "myproj.toml"
    proj_file.write_text('owner = "acme"\nrepo = "tool"\nimage = "img:v1"\ngithub_keyring_key = "k"\nbackend = "anthropic"\n')
    proj = Project.load("myproj", _DEFAULTS, config_dir=tmp_path)
    assert proj.name == "myproj"


def test_project_load_uses_projects_dir_name_constant(tmp_path: Path) -> None:
    # Project domain owns path construction: file must live at <config_dir>/PROJECTS_DIR_NAME/<name>.toml.
    projects_subdir = tmp_path / PROJECTS_DIR_NAME
    projects_subdir.mkdir()
    (projects_subdir / "alpha.toml").write_text(
        'owner = "acme"\nrepo = "tool"\nimage = "img:v1"\ngithub_keyring_key = "k"\nbackend = "anthropic"\n'
    )
    proj = Project.load("alpha", _DEFAULTS, config_dir=tmp_path)
    assert proj.name == "alpha"
    # A file placed outside PROJECTS_DIR_NAME is not found.
    (tmp_path / "alpha.toml").write_text(
        'owner = "acme"\nrepo = "tool"\nimage = "img:v1"\ngithub_keyring_key = "k"\nbackend = "anthropic"\n'
    )
    with pytest.raises(ProjectNotFoundError):
        Project.load("alpha", _DEFAULTS, config_dir=projects_subdir)


# ---------------------------------------------------------------------------
# Project.load — missing file → ProjectNotFoundError
# ---------------------------------------------------------------------------


def test_project_load_missing_file_raises_project_not_found_error(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    with pytest.raises(ProjectNotFoundError):
        Project.load("missing", _DEFAULTS, config_dir=tmp_path)


# ---------------------------------------------------------------------------
# Project.load — invalid project name → InvalidFileNameError
# ---------------------------------------------------------------------------


def test_project_load_path_traversal_raises_invalid_file_name_error(tmp_path: Path) -> None:
    with pytest.raises(InvalidFileNameError):
        Project.load("../escape", _DEFAULTS, config_dir=tmp_path)


def test_project_load_separator_in_name_raises_invalid_file_name_error(tmp_path: Path) -> None:
    with pytest.raises(InvalidFileNameError):
        Project.load("a/b", _DEFAULTS, config_dir=tmp_path)


def test_project_load_empty_name_raises_invalid_file_name_error(tmp_path: Path) -> None:
    with pytest.raises(InvalidFileNameError):
        Project.load("", _DEFAULTS, config_dir=tmp_path)


def test_project_load_dotted_name_raises_invalid_file_name_error(tmp_path: Path) -> None:
    with pytest.raises(InvalidFileNameError):
        Project.load("a.b", _DEFAULTS, config_dir=tmp_path)


# ---------------------------------------------------------------------------
# Project.load — TOML parse error
# ---------------------------------------------------------------------------


def test_project_load_parse_error_raises_toml_parse_error(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "bad.toml").write_text("owner = [unclosed\n")
    with pytest.raises(TomlParseError):
        Project.load("bad", _DEFAULTS, config_dir=tmp_path)


# ---------------------------------------------------------------------------
# Project.load — schema validation error (unknown key)
# ---------------------------------------------------------------------------


def test_project_load_unknown_key_raises_schema_validation_error(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    proj_file = tmp_path / "projects" / "extra.toml"
    proj_file.write_text(
        'owner = "nightjarrr"\n'
        'repo = "adda-dev-launcher"\n'
        'image = "ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0"\n'
        'github_keyring_key = "demo-token"\n'
        'backend = "anthropic"\n'
        'unknown_key = "oops"\n'
    )
    with pytest.raises(SchemaValidationError):
        Project.load("extra", _DEFAULTS, config_dir=tmp_path)


# ---------------------------------------------------------------------------
# Project.load — schema validation error (missing required field)
# ---------------------------------------------------------------------------


def test_project_load_missing_backend_raises_schema_validation_error(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    proj_file = tmp_path / "projects" / "nobk.toml"
    proj_file.write_text(
        'owner = "nightjarrr"\n'
        'repo = "adda-dev-launcher"\n'
        'image = "ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0"\n'
        'github_keyring_key = "demo-token"\n'
    )
    with pytest.raises(SchemaValidationError):
        Project.load("nobk", _DEFAULTS, config_dir=tmp_path)


# ---------------------------------------------------------------------------
# Integration: AppConfig + Project.load (resolution chain)
# ---------------------------------------------------------------------------


def test_integration_app_config_and_project_load(tmp_path: Path) -> None:
    # Write a config.toml with non-default project_defaults
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[project_defaults.tmpfs]\nhome = "2g"\n')

    # Write a project with a partial tmpfs override
    (tmp_path / "projects").mkdir()
    proj_file = tmp_path / "projects" / "myproj.toml"
    proj_file.write_text(
        'owner = "acme"\n'
        'repo = "my-repo"\n'
        'image = "ghcr.io/acme/my-repo:v1.0.0"\n'
        'github_keyring_key = "repo-token"\n'
        'backend = "anthropic"\n'
        "[tmpfs]\n"
        'workspace = "4g"\n'
    )

    app = AppConfig.load(config_dir=tmp_path)
    proj = Project.load("myproj", app.project_defaults, config_dir=tmp_path)

    # workspace overridden by project; home from app config; tmp from built-in default
    assert proj.tmpfs.workspace == "4g"
    assert proj.tmpfs.home == "2g"
    assert proj.tmpfs.tmp == "256m"
