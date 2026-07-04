"""
Tests for infra/project.py: ProjectFileModel validation, TomlProjectRepository paths.
"""

from pathlib import Path

import pytest

from adda_dev.domain.github import GitHub
from adda_dev.domain.llm import LlmProvider
from adda_dev.domain.project import ProjectNotFoundError
from adda_dev.infra.config import ProjectDefaults
from adda_dev.infra.project import PROJECTS_DIR_NAME, ProjectFileModel, TomlProjectRepository
from adda_dev.infra.store import InvalidFileNameError, SchemaValidationError, TomlParseError
from tests.conftest import FakeSecretSource

DATA_DIR = Path(__file__).parent / "data"

# Shared defaults using built-in values.
_DEFAULTS = ProjectDefaults()

# Non-default defaults to exercise override resolution.
_CUSTOM_DEFAULTS = ProjectDefaults.model_validate({"tmpfs": {"home": "1g", "workspace": "512m", "tmp": "128m"}})

_FAKE = FakeSecretSource()


def _repo(defaults: ProjectDefaults = _DEFAULTS) -> TomlProjectRepository:
    return TomlProjectRepository(defaults, _FAKE)


# ---------------------------------------------------------------------------
# ProjectFileModel — required fields
# ---------------------------------------------------------------------------


def _valid_file_data() -> dict[str, object]:
    return {
        "github": {"owner": "nightjarrr", "repo": "adda-dev-launcher", "secret_name": "demo-token"},
        "image": "ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0",
        "provider": "deepseek",
    }


def test_project_file_model_valid_minimal() -> None:
    pf = ProjectFileModel.model_validate(_valid_file_data())
    assert pf.github.owner == "nightjarrr"
    assert pf.provider == LlmProvider.deepseek
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


def test_project_file_model_missing_provider_rejected() -> None:
    data = _valid_file_data()
    del data["provider"]
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


def test_project_file_model_invalid_provider_rejected() -> None:
    data = _valid_file_data()
    data["provider"] = "openai"
    with pytest.raises(Exception):
        ProjectFileModel.model_validate(data)


# ---------------------------------------------------------------------------
# TomlProjectRepository.get — tmpfs resolution: no override → defaults pass through
# ---------------------------------------------------------------------------


def test_toml_project_repository_no_tmpfs_override_uses_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()
    (config_root / "projects").mkdir()
    (config_root / "projects" / "demo.toml").write_text(
        'image = "img:v1"\nprovider = "deepseek"\n[github]\nowner = "a"\nrepo = "b"\nsecret_name = "k"\n'
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    proj = _repo(_CUSTOM_DEFAULTS).get("demo")
    assert proj.tmpfs.home == "1g"
    assert proj.tmpfs.workspace == "512m"
    assert proj.tmpfs.tmp == "128m"


def test_toml_project_repository_no_tmpfs_override_uses_builtin_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()
    (config_root / "projects").mkdir()
    (config_root / "projects" / "demo.toml").write_text(
        'image = "img:v1"\nprovider = "deepseek"\n[github]\nowner = "a"\nrepo = "b"\nsecret_name = "k"\n'
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    proj = _repo().get("demo")
    assert proj.tmpfs.home == "512m"
    assert proj.tmpfs.workspace == "256m"
    assert proj.tmpfs.tmp == "256m"


# ---------------------------------------------------------------------------
# TomlProjectRepository.get — full tmpfs override
# ---------------------------------------------------------------------------


def test_toml_project_repository_full_tmpfs_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()
    (config_root / "projects").mkdir()
    (config_root / "projects" / "demo.toml").write_text(
        'image = "img:v1"\nprovider = "deepseek"\n[github]\nowner = "a"\nrepo = "b"\nsecret_name = "k"\n'
        '[tmpfs]\nhome = "2g"\nworkspace = "1g"\ntmp = "512m"\n'
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    proj = _repo().get("demo")
    assert proj.tmpfs.home == "2g"
    assert proj.tmpfs.workspace == "1g"
    assert proj.tmpfs.tmp == "512m"


# ---------------------------------------------------------------------------
# TomlProjectRepository.get — partial tmpfs override (field-wise merge)
# ---------------------------------------------------------------------------


def test_toml_project_repository_partial_tmpfs_override_workspace_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()
    (config_root / "projects").mkdir()
    (config_root / "projects" / "demo.toml").write_text(
        'image = "img:v1"\nprovider = "deepseek"\n[github]\nowner = "a"\nrepo = "b"\nsecret_name = "k"\n'
        '[tmpfs]\nworkspace = "2g"\n'
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    proj = _repo(_CUSTOM_DEFAULTS).get("demo")
    assert proj.tmpfs.workspace == "2g"
    assert proj.tmpfs.home == "1g"
    assert proj.tmpfs.tmp == "128m"


def test_toml_project_repository_partial_tmpfs_override_home_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()
    (config_root / "projects").mkdir()
    (config_root / "projects" / "demo.toml").write_text(
        'image = "img:v1"\nprovider = "deepseek"\n[github]\nowner = "a"\nrepo = "b"\nsecret_name = "k"\n[tmpfs]\nhome = "4g"\n'
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    proj = _repo().get("demo")
    assert proj.tmpfs.home == "4g"
    assert proj.tmpfs.workspace == "256m"
    assert proj.tmpfs.tmp == "256m"


# ---------------------------------------------------------------------------
# TomlProjectRepository.get — github and identity fields pass through
# ---------------------------------------------------------------------------


def test_toml_project_repository_github_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()
    (config_root / "projects").mkdir()
    (config_root / "projects" / "myproj.toml").write_text(
        'image = "ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0"\nprovider = "deepseek"\n'
        '[github]\nowner = "nightjarrr"\nrepo = "adda-dev-launcher"\nsecret_name = "demo-token"\n'
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    proj = _repo().get("myproj")
    assert proj.name == "myproj"
    assert proj.github.owner == "nightjarrr"
    assert proj.github.repo == "adda-dev-launcher"
    assert proj.github.secret_name == "demo-token"
    assert proj.image == "ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0"
    assert proj.provider == LlmProvider.deepseek


def test_toml_project_repository_constructs_github_domain_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()
    (config_root / "projects").mkdir()
    (config_root / "projects" / "demo.toml").write_text(
        'image = "img:v1"\nprovider = "deepseek"\n[github]\nowner = "a"\nrepo = "b"\nsecret_name = "k"\n'
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    proj = _repo().get("demo")
    assert isinstance(proj.github, GitHub)


# ---------------------------------------------------------------------------
# TomlProjectRepository.get — valid project file
# ---------------------------------------------------------------------------


def test_toml_project_repository_valid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()
    (config_root / "projects").mkdir()
    proj_file = config_root / "projects" / "demo.toml"
    proj_file.write_text(
        'image = "ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0"\n'
        'provider = "anthropic"\n'
        "[github]\n"
        'owner = "nightjarrr"\n'
        'repo = "adda-dev-launcher"\n'
        'secret_name = "demo-token"\n'
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    proj = _repo().get("demo")
    assert proj.name == "demo"
    assert proj.provider == LlmProvider.anthropic
    assert proj.tmpfs.home == "512m"


def test_toml_project_repository_from_static_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(DATA_DIR))
    proj = _repo().get("demo")
    assert proj.name == "demo"
    assert proj.provider == LlmProvider.deepseek
    assert proj.tmpfs.workspace == "2g"
    # home and tmp from built-in defaults
    assert proj.tmpfs.home == "512m"
    assert proj.tmpfs.tmp == "256m"
    assert proj.github.owner == "nightjarrr"
    assert proj.github.repo == "adda-dev-launcher"
    assert proj.github.secret_name == "demo-token"


# ---------------------------------------------------------------------------
# TomlProjectRepository.get — builds correct path
# ---------------------------------------------------------------------------


def test_toml_project_repository_builds_correct_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()
    (config_root / "projects").mkdir()
    proj_file = config_root / "projects" / "myproj.toml"
    proj_file.write_text(
        'image = "img:v1"\nprovider = "anthropic"\n[github]\nowner = "acme"\nrepo = "tool"\nsecret_name = "k"\n'
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    proj = _repo().get("myproj")
    assert proj.name == "myproj"


def test_toml_project_repository_uses_projects_dir_name_constant(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # get() owns path construction: file must live at <config_root>/PROJECTS_DIR_NAME/<name>.toml.
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()
    projects_subdir = config_root / PROJECTS_DIR_NAME
    projects_subdir.mkdir()
    (projects_subdir / "alpha.toml").write_text(
        'image = "img:v1"\nprovider = "anthropic"\n[github]\nowner = "acme"\nrepo = "tool"\nsecret_name = "k"\n'
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    proj = _repo().get("alpha")
    assert proj.name == "alpha"
    # A file placed directly under config_root (not in projects/) is not found.
    (config_root / "alpha.toml").write_text(
        'image = "img:v1"\nprovider = "anthropic"\n[github]\nowner = "acme"\nrepo = "tool"\nsecret_name = "k"\n'
    )
    with pytest.raises(ProjectNotFoundError):
        # Remove the projects/ subdir so the correctly-named file in the wrong place is not found.
        import shutil

        shutil.rmtree(projects_subdir)
        _repo().get("alpha")


# ---------------------------------------------------------------------------
# TomlProjectRepository.get — missing file → ProjectNotFoundError
# ---------------------------------------------------------------------------


def test_toml_project_repository_missing_file_raises_project_not_found_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()
    (config_root / "projects").mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with pytest.raises(ProjectNotFoundError):
        _repo().get("missing")


# ---------------------------------------------------------------------------
# TomlProjectRepository.get — invalid project name → InvalidFileNameError
# ---------------------------------------------------------------------------


def test_toml_project_repository_path_traversal_raises_invalid_file_name_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with pytest.raises(InvalidFileNameError):
        _repo().get("../escape")


def test_toml_project_repository_separator_in_name_raises_invalid_file_name_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with pytest.raises(InvalidFileNameError):
        _repo().get("a/b")


def test_toml_project_repository_empty_name_raises_invalid_file_name_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with pytest.raises(InvalidFileNameError):
        _repo().get("")


def test_toml_project_repository_dotted_name_raises_invalid_file_name_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with pytest.raises(InvalidFileNameError):
        _repo().get("a.b")


# ---------------------------------------------------------------------------
# TomlProjectRepository.get — TOML parse error
# ---------------------------------------------------------------------------


def test_toml_project_repository_parse_error_raises_toml_parse_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()
    (config_root / "projects").mkdir()
    (config_root / "projects" / "bad.toml").write_text("owner = [unclosed\n")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with pytest.raises(TomlParseError):
        _repo().get("bad")


# ---------------------------------------------------------------------------
# TomlProjectRepository.get — schema validation error (unknown key)
# ---------------------------------------------------------------------------


def test_toml_project_repository_unknown_key_raises_schema_validation_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()
    (config_root / "projects").mkdir()
    proj_file = config_root / "projects" / "extra.toml"
    proj_file.write_text(
        'image = "ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0"\n'
        'provider = "anthropic"\n'
        'unknown_key = "oops"\n'
        "[github]\n"
        'owner = "nightjarrr"\n'
        'repo = "adda-dev-launcher"\n'
        'secret_name = "demo-token"\n'
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with pytest.raises(SchemaValidationError):
        _repo().get("extra")


# ---------------------------------------------------------------------------
# TomlProjectRepository.get — schema validation error (missing required field)
# ---------------------------------------------------------------------------


def test_toml_project_repository_missing_provider_raises_schema_validation_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()
    (config_root / "projects").mkdir()
    proj_file = config_root / "projects" / "nobk.toml"
    proj_file.write_text(
        'image = "ghcr.io/nightjarrr/adda-dev-launcher:v0.1.0"\n'
        "[github]\n"
        'owner = "nightjarrr"\n'
        'repo = "adda-dev-launcher"\n'
        'secret_name = "demo-token"\n'
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with pytest.raises(SchemaValidationError):
        _repo().get("nobk")


# ---------------------------------------------------------------------------
# Integration: AppConfig + TomlProjectRepository (resolution chain)
# ---------------------------------------------------------------------------


def test_integration_app_config_and_toml_project_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()

    # Write a config.toml with non-default project_defaults
    cfg_file = config_root / "config.toml"
    cfg_file.write_text('[project_defaults.tmpfs]\nhome = "2g"\n')

    # Write a project with a partial tmpfs override
    (config_root / "projects").mkdir()
    proj_file = config_root / "projects" / "myproj.toml"
    proj_file.write_text(
        'image = "ghcr.io/acme/my-repo:v1.0.0"\n'
        'provider = "anthropic"\n'
        "[github]\n"
        'owner = "acme"\n'
        'repo = "my-repo"\n'
        'secret_name = "repo-token"\n'
        "[tmpfs]\n"
        'workspace = "4g"\n'
    )

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    from adda_dev.infra.config import load_app_config

    app_config = load_app_config()
    proj = TomlProjectRepository(app_config.project_defaults, _FAKE).get("myproj")

    # workspace overridden by project; home from app config; tmp from built-in default
    assert proj.tmpfs.workspace == "4g"
    assert proj.tmpfs.home == "2g"
    assert proj.tmpfs.tmp == "256m"
    assert proj.github.owner == "acme"
    assert proj.github.secret_name == "repo-token"
