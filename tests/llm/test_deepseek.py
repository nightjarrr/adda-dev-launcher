"""
Tests for llm/deepseek.py: DeepSeekConfigModel and DeepSeekBackend.
"""

import pytest

from adda_dev.credentials import SecretError
from adda_dev.llm.deepseek import DeepSeekBackend, DeepSeekConfigModel
from tests.test_credentials import FakeSecretStore

# ---------------------------------------------------------------------------
# DeepSeekConfigModel — defaults (verbatim from adda-dev.sh)
# ---------------------------------------------------------------------------


def test_deepseek_config_model_defaults() -> None:
    cfg = DeepSeekConfigModel()
    assert cfg.secret_name == "apikey"
    assert cfg.base_url == "https://api.deepseek.com/anthropic"
    assert cfg.model == "deepseek-v4-flash"
    assert cfg.opus_model == "deepseek-v4-pro[1m]"
    assert cfg.sonnet_model == "deepseek-v4-pro[1m]"
    assert cfg.haiku_model == "deepseek-v4-flash"
    assert cfg.subagent_model == "deepseek-v4-flash"
    assert cfg.effort_level == "max"


def test_deepseek_config_model_override_secret_name() -> None:
    cfg = DeepSeekConfigModel(secret_name="ds-key")
    assert cfg.secret_name == "ds-key"


def test_deepseek_config_model_extra_field_rejected() -> None:
    with pytest.raises(Exception):
        DeepSeekConfigModel.model_validate({"unknown": "x"})


# ---------------------------------------------------------------------------
# DeepSeekBackend — from_config and get_secret
# ---------------------------------------------------------------------------


def test_deepseek_backend_from_config_maps_all_fields() -> None:
    cfg = DeepSeekConfigModel(secret_name="ds-key")
    backend = DeepSeekBackend.from_config(cfg)
    assert backend.secret_name == "ds-key"
    assert backend.base_url == "https://api.deepseek.com/anthropic"
    assert backend.model == "deepseek-v4-flash"
    assert backend.opus_model == "deepseek-v4-pro[1m]"
    assert backend.sonnet_model == "deepseek-v4-pro[1m]"
    assert backend.haiku_model == "deepseek-v4-flash"
    assert backend.subagent_model == "deepseek-v4-flash"
    assert backend.effort_level == "max"


def test_deepseek_backend_get_secret_returns_value() -> None:
    fake = FakeSecretStore({("adda-dev:deepseek", "apikey"): "ds-token"})
    backend = DeepSeekBackend.from_config(DeepSeekConfigModel())
    backend_with_store = DeepSeekBackend(
        secret_name=backend.secret_name,
        base_url=backend.base_url,
        model=backend.model,
        opus_model=backend.opus_model,
        sonnet_model=backend.sonnet_model,
        haiku_model=backend.haiku_model,
        subagent_model=backend.subagent_model,
        effort_level=backend.effort_level,
        store=fake,
    )
    assert backend_with_store.get_secret() == "ds-token"


def test_deepseek_backend_get_secret_raises_on_missing() -> None:
    fake = FakeSecretStore()
    cfg = DeepSeekConfigModel()
    backend = DeepSeekBackend(
        secret_name=cfg.secret_name,
        base_url=cfg.base_url,
        model=cfg.model,
        opus_model=cfg.opus_model,
        sonnet_model=cfg.sonnet_model,
        haiku_model=cfg.haiku_model,
        subagent_model=cfg.subagent_model,
        effort_level=cfg.effort_level,
        store=fake,
    )
    with pytest.raises(SecretError):
        backend.get_secret()


def test_deepseek_backend_service_namespace() -> None:
    assert DeepSeekBackend._service == "adda-dev:deepseek"


def test_deepseek_backend_frozen() -> None:
    cfg = DeepSeekConfigModel()
    backend = DeepSeekBackend.from_config(cfg)
    with pytest.raises(Exception):
        backend.secret_name = "changed"  # type: ignore[misc]
