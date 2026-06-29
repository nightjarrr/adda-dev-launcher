"""
Tests for infra/project.py: ProjectFileModel validation, load_project() paths.
"""

from pathlib import Path

import pytest

from adda_dev.domain.github import GitHub
from adda_dev.domain.llm import LlmBackend
from adda_dev.domain.project import ProjectNotFoundError
from adda_dev.infra.config import ProjectDefaults
from adda_dev.infra.project import PROJECTS_DIR_NAME, ProjectFileModel, load_project
from adda_dev.infra.store import InvalidFileNameError, SchemaValidationError, TomlParseError
from tests.conftest import FakeSecretSource

DATA_DIR = Path(__file__).parent / "data" / "config"

# Shared defaults using built-in values.
_DEFAULTS = ProjectDefaults()

# Non-default defaults to exercise override resolution.
_CUSTOM_DEFAULTS = ProjectDefaults.model_validate({"tmpfs": {"home": "1g", "workspace": "512m", "tmp": "128m"}})

_FAKE = FakeSecretSource()


# ---------------------------------------------------------------------------
# ProjectFileModel — required fields
# ---------------------------------------------------------------------------


def _valid_file_data() -> dict[str, object]:
    return {
        "github": {"owner": "nightjarrr", "repo": "adda-dev-launcher", "secret_name": "demo-token"},
        "image": "ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0",
        "backend": "deepseek",
    }


def test_project_file_model_valid_minimal() -> None:
    pf = ProjectFileModel.model_validate(_valid_file_data())
    assert pf.github.owner == "nightjarrr"
    assert pf.backend == LlmBackend.deepseek
    assert pf.tmpfs is None


def test_project_file_model_valid_with_tmpfs() -> None:
    data = _valid_file_data()
    data["tmpfs"] = {"workspace": "2g"}
    pf = ProjectFileModel.model_validate(data)
    assert pf.tmpfs is not None
    assert pf.tmpfs.workspace == "2g"
    assert pf.tmpfs.home is None


def test_project_file_model_missing_github_rejected() -> None:
    data = _valid_file_data()
    del data["github"]
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


def test_project_file_model_unknown_key_rejected() -> None:
    data = _valid_file_data()
    data["unknown"] = "value"
    with pytest.raises(Exception):
        ProjectFileModel.model_validate(data)


def test_project_file_model_invalid_backend_rejected() -> None:
    data = _valid_file_data()
    data["backend"] = "openai"
    with pytest.raises(Exception):
        ProjectFileModel.model_validate(data)


# ---------------------------------------------------------------------------
# load_project — tmpfs resolution: no override → defaults pass through
# ---------------------------------------------------------------------------


def test_load_project_no_tmpfs_override_uses_defaults(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "demo.toml").write_text(
        'image = "img:v1"\nbackend = "deepseek"\n[github]\nowner = "a"\nrepo = "b"\nsecret_name = "k"\n'
    )
    proj = load_project("demo", _CUSTOM_DEFAULTS, _FAKE, config_dir=tmp_path)
    assert proj.tmpfs.home == "1g"
    assert proj.tmpfs.workspace == "512m"
    assert proj.tmpfs.tmp == "128m"


def test_load_project_no_tmpfs_override_uses_builtin_defaults(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "demo.toml").write_text(
        'image = "img:v1"\nbackend = "deepseek"\n[github]\nowner = "a"\nrepo = "b"\nsecret_name = "k"\n'
    )
    proj = load_project("demo", _DEFAULTS, _FAKE, config_dir=tmp_path)
    assert proj.tmpfs.home == "512m"
    assert proj.tmpfs.workspace == "256m"
    assert proj.tmpfs.tmp == "256m"


# ---------------------------------------------------------------------------
# load_project — full tmpfs override
# ---------------------------------------------------------------------------


def test_load_project_full_tmpfs_override(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "demo.toml").write_text(
        'image = "img:v1"\nbackend = "deepseek"\n[github]\nowner = "a"\nrepo = "b"\nsecret_name = "k"\n'
        '[tmpfs]\nhome = "2g"\nworkspace = "1g"\ntmp = "512m"\n'
    )
    proj = load_project("demo", _DEFAULTS, _FAKE, config_dir=tmp_path)
    assert proj.tmpfs.home == "2g"
    assert proj.tmpfs.workspace == "1g"
    assert proj.tmpfs.tmp == "512m"


# ---------------------------------------------------------------------------
# load_project — partial tmpfs override (field-wise merge)
# ---------------------------------------------------------------------------


def test_load_project_partial_tmpfs_override_workspace_only(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "demo.toml").write_text(
        'image = "img:v1"\nbackend = "deepseek"\n[github]\nowner = "a"\nrepo = "b"\nsecret_name = "k"\n'
        '[tmpfs]\nworkspace = "2g"\n'
    )
    proj = load_project("demo", _CUSTOM_DEFAULTS, _FAKE, config_dir=tmp_path)
    assert proj.tmpfs.workspace == "2g"
    assert proj.tmpfs.home == "1g"
    assert proj.tmpfs.tmp == "128m"


def test_load_project_partial_tmpfs_override_home_only(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "demo.toml").write_text(
        'image = "img:v1"\nbackend = "deepseek"\n[github]\nowner = "a"\nrepo = "b"\nsecret_name = "k"\n[tmpfs]\nhome = "4g"\n'
    )
    proj = load_project("demo", _DEFAULTS, _FAKE, config_dir=tmp_path)
    assert proj.tmpfs.home == "4g"
    assert proj.tmpfs.workspace == "256m"
    assert proj.tmpfs.tmp == "256m"


# ---------------------------------------------------------------------------
# load_project — github and identity fields pass through
# ---------------------------------------------------------------------------


def test_load_project_github_fields(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "myproj.toml").write_text(
        'image = "ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0"\nbackend = "deepseek"\n'
        '[github]\nowner = "nightjarrr"\nrepo = "adda-dev-launcher"\nsecret_name = "demo-token"\n'
    )
    proj = load_project("myproj", _DEFAULTS, _FAKE, config_dir=tmp_path)
    assert proj.name == "myproj"
    assert proj.github.owner == "nightjarrr"
    assert proj.github.repo == "adda-dev-launcher"
    assert proj.github.secret_name == "demo-token"
    assert proj.image == "ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0"
    assert proj.backend == LlmBackend.deepseek


def test_load_project_constructs_github_domain_model(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "demo.toml").write_text(
        'image = "img:v1"\nbackend = "deepseek"\n[github]\nowner = "a"\nrepo = "b"\nsecret_name = "k"\n'
    )
    proj = load_project("demo", _DEFAULTS, _FAKE, config_dir=tmp_path)
    assert isinstance(proj.github, GitHub)


# ---------------------------------------------------------------------------
# load_project — valid project file
# ---------------------------------------------------------------------------


def test_load_project_valid(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    proj_file = tmp_path / "projects" / "demo.toml"
    proj_file.write_text(
        'image = "ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0"\n'
        'backend = "anthropic"\n'
        "[github]\n"
        'owner = "nightjarrr"\n'
        'repo = "adda-dev-launcher"\n'
        'secret_name = "demo-token"\n'
    )
    proj = load_project("demo", _DEFAULTS, _FAKE, config_dir=tmp_path)
    assert proj.name == "demo"
    assert proj.backend == LlmBackend.anthropic
    assert proj.tmpfs.home == "512m"


def test_load_project_from_static_fixture() -> None:
    proj = load_project("demo", _DEFAULTS, _FAKE, config_dir=DATA_DIR)
    assert proj.name == "demo"
    assert proj.backend == LlmBackend.deepseek
    assert proj.tmpfs.workspace == "2g"
    # home and tmp from built-in defaults
    assert proj.tmpfs.home == "512m"
    assert proj.tmpfs.tmp == "256m"
    assert proj.github.owner == "nightjarrr"
    assert proj.github.repo == "adda-dev-launcher"
    assert proj.github.secret_name == "demo-token"


# ---------------------------------------------------------------------------
# load_project — builds correct path (entity owns <name>.toml naming)
# ---------------------------------------------------------------------------


def test_load_project_builds_correct_path(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    proj_file = tmp_path / "projects" / "myproj.toml"
    proj_file.write_text(
        'image = "img:v1"\nbackend = "anthropic"\n[github]\nowner = "acme"\nrepo = "tool"\nsecret_name = "k"\n'
    )
    proj = load_project("myproj", _DEFAULTS, _FAKE, config_dir=tmp_path)
    assert proj.name == "myproj"


def test_load_project_uses_projects_dir_name_constant(tmp_path: Path) -> None:
    # load_project owns path construction: file must live at <config_dir>/PROJECTS_DIR_NAME/<name>.toml.
    projects_subdir = tmp_path / PROJECTS_DIR_NAME
    projects_subdir.mkdir()
    (projects_subdir / "alpha.toml").write_text(
        'image = "img:v1"\nbackend = "anthropic"\n[github]\nowner = "acme"\nrepo = "tool"\nsecret_name = "k"\n'
    )
    proj = load_project("alpha", _DEFAULTS, _FAKE, config_dir=tmp_path)
    assert proj.name == "alpha"
    # A file placed outside PROJECTS_DIR_NAME is not found.
    (tmp_path / "alpha.toml").write_text(
        'image = "img:v1"\nbackend = "anthropic"\n[github]\nowner = "acme"\nrepo = "tool"\nsecret_name = "k"\n'
    )
    with pytest.raises(ProjectNotFoundError):
        load_project("alpha", _DEFAULTS, _FAKE, config_dir=projects_subdir)


# ---------------------------------------------------------------------------
# load_project — missing file → ProjectNotFoundError
# ---------------------------------------------------------------------------


def test_load_project_missing_file_raises_project_not_found_error(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    with pytest.raises(ProjectNotFoundError):
        load_project("missing", _DEFAULTS, _FAKE, config_dir=tmp_path)


# ---------------------------------------------------------------------------
# load_project — invalid project name → InvalidFileNameError
# ---------------------------------------------------------------------------


def test_load_project_path_traversal_raises_invalid_file_name_error(tmp_path: Path) -> None:
    with pytest.raises(InvalidFileNameError):
        load_project("../escape", _DEFAULTS, _FAKE, config_dir=tmp_path)


def test_load_project_separator_in_name_raises_invalid_file_name_error(tmp_path: Path) -> None:
    with pytest.raises(InvalidFileNameError):
        load_project("a/b", _DEFAULTS, _FAKE, config_dir=tmp_path)


def test_load_project_empty_name_raises_invalid_file_name_error(tmp_path: Path) -> None:
    with pytest.raises(InvalidFileNameError):
        load_project("", _DEFAULTS, _FAKE, config_dir=tmp_path)


def test_load_project_dotted_name_raises_invalid_file_name_error(tmp_path: Path) -> None:
    with pytest.raises(InvalidFileNameError):
        load_project("a.b", _DEFAULTS, _FAKE, config_dir=tmp_path)


# ---------------------------------------------------------------------------
# load_project — TOML parse error
# ---------------------------------------------------------------------------


def test_load_project_parse_error_raises_toml_parse_error(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "bad.toml").write_text("owner = [unclosed\n")
    with pytest.raises(TomlParseError):
        load_project("bad", _DEFAULTS, _FAKE, config_dir=tmp_path)


# ---------------------------------------------------------------------------
# load_project — schema validation error (unknown key)
# ---------------------------------------------------------------------------


def test_load_project_unknown_key_raises_schema_validation_error(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    proj_file = tmp_path / "projects" / "extra.toml"
    proj_file.write_text(
        'image = "ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0"\n'
        'backend = "anthropic"\n'
        'unknown_key = "oops"\n'
        "[github]\n"
        'owner = "nightjarrr"\n'
        'repo = "adda-dev-launcher"\n'
        'secret_name = "demo-token"\n'
    )
    with pytest.raises(SchemaValidationError):
        load_project("extra", _DEFAULTS, _FAKE, config_dir=tmp_path)


# ---------------------------------------------------------------------------
# load_project — schema validation error (missing required field)
# ---------------------------------------------------------------------------


def test_load_project_missing_backend_raises_schema_validation_error(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    proj_file = tmp_path / "projects" / "nobk.toml"
    proj_file.write_text(
        'image = "ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0"\n'
        "[github]\n"
        'owner = "nightjarrr"\n'
        'repo = "adda-dev-launcher"\n'
        'secret_name = "demo-token"\n'
    )
    with pytest.raises(SchemaValidationError):
        load_project("nobk", _DEFAULTS, _FAKE, config_dir=tmp_path)


# ---------------------------------------------------------------------------
# Integration: AppConfig + load_project (resolution chain)
# ---------------------------------------------------------------------------


def test_integration_app_config_and_load_project(tmp_path: Path) -> None:
    # Write a config.toml with non-default project_defaults
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[project_defaults.tmpfs]\nhome = "2g"\n')

    # Write a project with a partial tmpfs override
    (tmp_path / "projects").mkdir()
    proj_file = tmp_path / "projects" / "myproj.toml"
    proj_file.write_text(
        'image = "ghcr.io/acme/my-repo:v1.0.0"\n'
        'backend = "anthropic"\n'
        "[github]\n"
        'owner = "acme"\n'
        'repo = "my-repo"\n'
        'secret_name = "repo-token"\n'
        "[tmpfs]\n"
        'workspace = "4g"\n'
    )

    from adda_dev.infra.config import load_app_config

    app = load_app_config(config_dir=tmp_path)
    proj = load_project("myproj", app.project_defaults, _FAKE, config_dir=tmp_path)

    # workspace overridden by project; home from app config; tmp from built-in default
    assert proj.tmpfs.workspace == "4g"
    assert proj.tmpfs.home == "2g"
    assert proj.tmpfs.tmp == "256m"
    assert proj.github.owner == "acme"
    assert proj.github.secret_name == "repo-token"
