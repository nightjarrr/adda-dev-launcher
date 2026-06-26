"""
Tests for app_config.py: ContainerEngine, ProjectDefaults, AppConfig load paths.
"""

from pathlib import Path

import pytest

from adda_dev.app_config import DEFAULT_ENVOY_IMAGE, AppConfig, ContainerEngine, ProjectDefaults
from adda_dev.store import SchemaValidationError, TomlParseError
from adda_dev.tmpfs import TmpfsSizes

DATA_DIR = Path(__file__).parent / "data" / "config"


# ---------------------------------------------------------------------------
# ContainerEngine enum
# ---------------------------------------------------------------------------


def test_container_engine_members() -> None:
    assert ContainerEngine.docker == "docker"
    assert ContainerEngine.podman == "podman"


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
    assert cfg.container_engine == ContainerEngine.docker
    assert cfg.envoy_image == DEFAULT_ENVOY_IMAGE
    assert cfg.envoy_image == "envoyproxy/envoy:v1.33.14"
    assert cfg.tmux_config_path is None
    assert cfg.llm.anthropic.keyring_key == "oauth"
    assert cfg.llm.deepseek.keyring_key == "apikey"
    assert cfg.project_defaults.tmpfs.home == "512m"


def test_app_config_bad_enum_rejected() -> None:
    with pytest.raises(Exception):
        AppConfig.model_validate({"container_engine": "lxc"})


def test_app_config_unknown_key_rejected() -> None:
    with pytest.raises(Exception):
        AppConfig.model_validate({"unknown_key": "value"})


# ---------------------------------------------------------------------------
# AppConfig.load — missing file → defaults
# ---------------------------------------------------------------------------


def test_app_config_load_missing_file_returns_defaults(tmp_path: Path) -> None:
    cfg = AppConfig.load(config_dir=tmp_path)
    assert cfg.container_engine == ContainerEngine.docker
    assert cfg.envoy_image == DEFAULT_ENVOY_IMAGE


# ---------------------------------------------------------------------------
# AppConfig.load — present valid file
# ---------------------------------------------------------------------------


def test_app_config_load_valid_file(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        'container_engine = "podman"\nenvoy_image = "envoyproxy/envoy:v1.34.0"\n[llm.deepseek]\nkeyring_key = "ds-key"\n'
    )
    cfg = AppConfig.load(config_dir=tmp_path)
    assert cfg.container_engine == ContainerEngine.podman
    assert cfg.envoy_image == "envoyproxy/envoy:v1.34.0"
    assert cfg.llm.deepseek.keyring_key == "ds-key"


def test_app_config_load_from_static_fixture() -> None:
    cfg = AppConfig.load(config_dir=DATA_DIR)
    assert cfg.container_engine == ContainerEngine.podman
    assert cfg.envoy_image == "envoyproxy/envoy:v1.34.0"
    assert cfg.llm.deepseek.keyring_key == "ds-key"
    assert cfg.project_defaults.tmpfs.home == "1g"


# ---------------------------------------------------------------------------
# AppConfig.load — TOML parse error
# ---------------------------------------------------------------------------


def test_app_config_load_parse_error(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text("container_engine = [unclosed\n")
    with pytest.raises(TomlParseError):
        AppConfig.load(config_dir=tmp_path)


# ---------------------------------------------------------------------------
# AppConfig.load — schema validation error
# ---------------------------------------------------------------------------


def test_app_config_load_schema_validation_error(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text('container_engine = "lxc"\n')
    with pytest.raises(SchemaValidationError):
        AppConfig.load(config_dir=tmp_path)


def test_app_config_load_unknown_key_error(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text('unknown_key = "value"\n')
    with pytest.raises(SchemaValidationError):
        AppConfig.load(config_dir=tmp_path)


# ---------------------------------------------------------------------------
# AppConfig.load — correct path (entity builds config.toml path)
# ---------------------------------------------------------------------------


def test_app_config_load_builds_config_toml_path(tmp_path: Path) -> None:
    # Only a file named config.toml should be loaded; a file with any other name is ignored.
    (tmp_path / "config.toml").write_text('envoy_image = "envoyproxy/envoy:v2.0.0"\n')
    (tmp_path / "other.toml").write_text('envoy_image = "should-not-load"\n')
    cfg = AppConfig.load(config_dir=tmp_path)
    assert cfg.envoy_image == "envoyproxy/envoy:v2.0.0"


# ---------------------------------------------------------------------------
# AppConfig.load — project_defaults.tmpfs partial override
# ---------------------------------------------------------------------------


def test_app_config_load_partial_tmpfs_defaults(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text('[project_defaults.tmpfs]\nhome = "1g"\n')
    cfg = AppConfig.load(config_dir=tmp_path)
    assert cfg.project_defaults.tmpfs.home == "1g"
    # other fields retain built-in defaults
    assert cfg.project_defaults.tmpfs.workspace == "256m"
    assert cfg.project_defaults.tmpfs.tmp == "256m"


# ---------------------------------------------------------------------------
# AppConfig.load — tmux_config_path
# ---------------------------------------------------------------------------


def test_app_config_load_tmux_config_path(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text('tmux_config_path = "/home/user/.tmux.conf"\n')
    cfg = AppConfig.load(config_dir=tmp_path)
    assert cfg.tmux_config_path == Path("/home/user/.tmux.conf")
