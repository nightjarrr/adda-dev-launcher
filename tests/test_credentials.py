"""
Tests for domain/credentials.py: SecretSource protocol, Secret ABC, SecretError.
Tests for infra/keyring_source.py: KeyringSecretSource.
"""

from dataclasses import dataclass
from typing import ClassVar
from unittest.mock import patch

import pytest

from adda_dev.domain.credentials import Secret, SecretError, SecretSource
from adda_dev.infra.keyring_source import KeyringSecretSource
from tests.conftest import FakeSecretSource

# ---------------------------------------------------------------------------
# KeyringSecretSource
# ---------------------------------------------------------------------------


def test_keyring_secret_source_returns_value_when_found() -> None:
    with patch("adda_dev.infra.keyring_source.keyring.get_password", return_value="my-token"):
        store = KeyringSecretSource()
        assert store.get("svc", "key") == "my-token"


def test_keyring_secret_source_raises_secret_error_when_not_found() -> None:
    with patch("adda_dev.infra.keyring_source.keyring.get_password", return_value=None):
        store = KeyringSecretSource()
        with pytest.raises(SecretError, match="No secret for 'svc'/'key'"):
            store.get("svc", "key")


# ---------------------------------------------------------------------------
# Secret ABC — concrete subclass via FakeSecretSource injection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ConcreteSecret(Secret):
    _service: ClassVar[str] = "test-service"

    secret_name: str
    source: SecretSource


def test_secret_get_secret_returns_value() -> None:
    fake = FakeSecretSource({("test-service", "my-key"): "secret-value"})
    obj = _ConcreteSecret(secret_name="my-key", source=fake)
    assert obj.get_secret() == "secret-value"


def test_secret_get_secret_raises_when_missing() -> None:
    fake = FakeSecretSource()
    obj = _ConcreteSecret(secret_name="missing-key", source=fake)
    with pytest.raises(SecretError):
        obj.get_secret()


def test_secret_error_is_adda_dev_error() -> None:
    from adda_dev.common import AddaDevError

    err = SecretError("oops")
    assert isinstance(err, AddaDevError)
