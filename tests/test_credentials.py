"""
Tests for credentials.py: SecretStore protocol, KeyringSecretStore, Secret ABC.
"""

from dataclasses import dataclass, field
from typing import ClassVar
from unittest.mock import patch

import pytest

from adda_dev.credentials import KeyringSecretStore, Secret, SecretError, SecretStore

# ---------------------------------------------------------------------------
# FakeSecretStore — test double for SecretStore
# ---------------------------------------------------------------------------


class FakeSecretStore(SecretStore):
    """SecretStore test double backed by a dict."""

    def __init__(self, secrets: dict[tuple[str, str], str] | None = None) -> None:
        self._secrets: dict[tuple[str, str], str] = secrets or {}

    def get(self, service: str, key: str) -> str:
        value = self._secrets.get((service, key))
        if value is None:
            raise SecretError(f"No secret for {service!r}/{key!r}")
        return value


# ---------------------------------------------------------------------------
# KeyringSecretStore
# ---------------------------------------------------------------------------


def test_keyring_secret_store_returns_value_when_found() -> None:
    with patch("adda_dev.credentials.keyring.get_password", return_value="my-token"):
        store = KeyringSecretStore()
        assert store.get("svc", "key") == "my-token"


def test_keyring_secret_store_raises_secret_error_when_not_found() -> None:
    with patch("adda_dev.credentials.keyring.get_password", return_value=None):
        store = KeyringSecretStore()
        with pytest.raises(SecretError, match="No secret for 'svc'/'key'"):
            store.get("svc", "key")


# ---------------------------------------------------------------------------
# Secret ABC — concrete subclass via FakeSecretStore injection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ConcreteSecret(Secret):
    _service: ClassVar[str] = "test-service"

    secret_name: str
    store: SecretStore = field(default_factory=KeyringSecretStore, repr=False, compare=False)


def test_secret_get_secret_returns_value() -> None:
    fake = FakeSecretStore({("test-service", "my-key"): "secret-value"})
    obj = _ConcreteSecret(secret_name="my-key", store=fake)
    assert obj.get_secret() == "secret-value"


def test_secret_get_secret_raises_when_missing() -> None:
    fake = FakeSecretStore()
    obj = _ConcreteSecret(secret_name="missing-key", store=fake)
    with pytest.raises(SecretError):
        obj.get_secret()


def test_secret_error_is_adda_dev_error() -> None:
    from adda_dev.common import AddaDevError

    err = SecretError("oops")
    assert isinstance(err, AddaDevError)
