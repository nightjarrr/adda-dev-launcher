"""
Tests for infra/config.py: ContainerEngineChoice, ProjectDefaults, load_app_config() paths.
"""

from pathlib import Path

import pytest

from adda_dev.domain.tmpfs import TmpfsSizes
from adda_dev.infra.config import DEFAULT_ENVOY_IMAGE, AppConfig, ContainerEngineChoice, ProjectDefaults, load_app_config
from adda_dev.infra.store import SchemaValidationError, TomlParseError

DATA_DIR = Path(__file__).parent / "data"


# ---------------------------------------------------------------------------
# ContainerEngineChoice enum
# ---------------------------------------------------------------------------


def test_container_engine_choice_members() -> None:
    assert ContainerEngineChoice.docker == "docker"
    assert ContainerEngineChoice.podman == "podman"


# ---------------------------------------------------------------------------
# ProjectDefaults — defaults
# ---------------------------------------------------------------------------


def test_project_defaults_defaults() -> None:
    pd = ProjectDefaults()
    assert isinstance(pd.tmpfs, TmpfsSizes)
    assert pd.tmpfs.home == "512m"
    assert pd.tmpfs.workspace == "256m"
    assert pd.tmpfs.tmp == "256m"


def test_project_defaults_extra_field_rejected() -> None:
    with pytest.raises(Exception):
        ProjectDefaults.model_validate({"tmpfs": {}, "unknown": True})


# ---------------------------------------------------------------------------
# AppConfig — defaults
# ---------------------------------------------------------------------------


def test_app_config_defaults() -> None:
    cfg = AppConfig()
    assert cfg.container_engine == ContainerEngineChoice.docker
    assert cfg.envoy_image == DEFAULT_ENVOY_IMAGE
    assert cfg.envoy_image == "envoyproxy/envoy:v1.33.14"
    assert cfg.llm.anthropic.secret_name == "oauth"
    assert cfg.llm.deepseek.secret_name == "apikey"
    assert cfg.project_defaults.tmpfs.home == "512m"


def test_app_config_bad_enum_rejected() -> None:
    with pytest.raises(Exception):
        AppConfig.model_validate({"container_engine": "lxc"})


def test_app_config_unknown_key_rejected() -> None:
    with pytest.raises(Exception):
        AppConfig.model_validate({"unknown_key": "value"})


# ---------------------------------------------------------------------------
# load_app_config — missing file → defaults
# ---------------------------------------------------------------------------


def test_load_app_config_missing_file_returns_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    cfg = load_app_config()
    assert cfg.container_engine == ContainerEngineChoice.docker
    assert cfg.envoy_image == DEFAULT_ENVOY_IMAGE


# ---------------------------------------------------------------------------
# load_app_config — present valid file
# ---------------------------------------------------------------------------


def test_load_app_config_valid_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()
    config_file = config_root / "config.toml"
    config_file.write_text(
        'container_engine = "podman"\nenvoy_image = "envoyproxy/envoy:v1.34.0"\n[llm.deepseek]\nsecret_name = "ds-key"\n'
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    cfg = load_app_config()
    assert cfg.container_engine == ContainerEngineChoice.podman
    assert cfg.envoy_image == "envoyproxy/envoy:v1.34.0"
    assert cfg.llm.deepseek.secret_name == "ds-key"


def test_load_app_config_from_static_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(DATA_DIR))
    cfg = load_app_config()
    assert cfg.container_engine == ContainerEngineChoice.podman
    assert cfg.envoy_image == "envoyproxy/envoy:v1.34.0"
    assert cfg.llm.deepseek.secret_name == "ds-key"
    assert cfg.project_defaults.tmpfs.home == "1g"


# ---------------------------------------------------------------------------
# load_app_config — TOML parse error
# ---------------------------------------------------------------------------


def test_load_app_config_parse_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()
    config_file = config_root / "config.toml"
    config_file.write_text("container_engine = [unclosed\n")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with pytest.raises(TomlParseError):
        load_app_config()


# ---------------------------------------------------------------------------
# load_app_config — schema validation error
# ---------------------------------------------------------------------------


def test_load_app_config_schema_validation_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()
    config_file = config_root / "config.toml"
    config_file.write_text('container_engine = "lxc"\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with pytest.raises(SchemaValidationError):
        load_app_config()


def test_load_app_config_unknown_key_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()
    config_file = config_root / "config.toml"
    config_file.write_text('unknown_key = "value"\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with pytest.raises(SchemaValidationError):
        load_app_config()


# ---------------------------------------------------------------------------
# load_app_config — correct path (entity builds config.toml path)
# ---------------------------------------------------------------------------


def test_load_app_config_builds_config_toml_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Only a file named config.toml should be loaded; a file with any other name is ignored.
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()
    (config_root / "config.toml").write_text('envoy_image = "envoyproxy/envoy:v2.0.0"\n')
    (config_root / "other.toml").write_text('envoy_image = "should-not-load"\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    cfg = load_app_config()
    assert cfg.envoy_image == "envoyproxy/envoy:v2.0.0"


# ---------------------------------------------------------------------------
# load_app_config — project_defaults.tmpfs partial override
# ---------------------------------------------------------------------------


def test_load_app_config_partial_tmpfs_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_root = tmp_path / "adda-dev"
    config_root.mkdir()
    config_file = config_root / "config.toml"
    config_file.write_text('[project_defaults.tmpfs]\nhome = "1g"\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    cfg = load_app_config()
    assert cfg.project_defaults.tmpfs.home == "1g"
    # other fields retain built-in defaults
    assert cfg.project_defaults.tmpfs.workspace == "256m"
    assert cfg.project_defaults.tmpfs.tmp == "256m"
