"""
Tests for domain/llm.py: DeepSeekBackend.
Tests for infra/llm.py: DeepSeekConfigModel.
"""

import pytest

from adda_dev.domain.credentials import SecretError
from adda_dev.domain.llm import DeepSeekBackend
from adda_dev.infra.llm import DeepSeekConfigModel
from tests.conftest import FakeSecretSource

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
# DeepSeekBackend — construction and get_secret
# ---------------------------------------------------------------------------


def _make_deepseek_backend(fake: FakeSecretSource, secret_name: str = "apikey") -> DeepSeekBackend:
    cfg = DeepSeekConfigModel(secret_name=secret_name)
    return DeepSeekBackend(
        secret_name=cfg.secret_name,
        base_url=cfg.base_url,
        model=cfg.model,
        opus_model=cfg.opus_model,
        sonnet_model=cfg.sonnet_model,
        haiku_model=cfg.haiku_model,
        subagent_model=cfg.subagent_model,
        effort_level=cfg.effort_level,
        source=fake,
    )


def test_deepseek_backend_fields_map_from_config() -> None:
    fake = FakeSecretSource()
    cfg = DeepSeekConfigModel(secret_name="ds-key")
    backend = DeepSeekBackend(
        secret_name=cfg.secret_name,
        base_url=cfg.base_url,
        model=cfg.model,
        opus_model=cfg.opus_model,
        sonnet_model=cfg.sonnet_model,
        haiku_model=cfg.haiku_model,
        subagent_model=cfg.subagent_model,
        effort_level=cfg.effort_level,
        source=fake,
    )
    assert backend.secret_name == "ds-key"
    assert backend.base_url == "https://api.deepseek.com/anthropic"
    assert backend.model == "deepseek-v4-flash"
    assert backend.opus_model == "deepseek-v4-pro[1m]"
    assert backend.sonnet_model == "deepseek-v4-pro[1m]"
    assert backend.haiku_model == "deepseek-v4-flash"
    assert backend.subagent_model == "deepseek-v4-flash"
    assert backend.effort_level == "max"


def test_deepseek_backend_get_secret_returns_value() -> None:
    fake = FakeSecretSource({("adda-dev:deepseek", "apikey"): "ds-token"})
    backend = _make_deepseek_backend(fake)
    assert backend.get_secret() == "ds-token"


def test_deepseek_backend_get_secret_raises_on_missing() -> None:
    fake = FakeSecretSource()
    backend = _make_deepseek_backend(fake)
    with pytest.raises(SecretError):
        backend.get_secret()


def test_deepseek_backend_service_namespace() -> None:
    assert DeepSeekBackend._service == "adda-dev:deepseek"


def test_deepseek_backend_frozen() -> None:
    fake = FakeSecretSource()
    backend = _make_deepseek_backend(fake)
    with pytest.raises(Exception):
        backend.secret_name = "changed"  # type: ignore[misc]
