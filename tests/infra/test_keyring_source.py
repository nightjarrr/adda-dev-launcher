"""Tests for adda_dev.infra.keyring_source."""

from unittest.mock import patch

import pytest
from keyring.errors import KeyringError, NoKeyringError

from adda_dev.domain.credentials import SecretError
from adda_dev.infra.keyring_source import KeyringSecretSource


def test_keyring_source_returns_secret() -> None:
    source = KeyringSecretSource()
    with patch("adda_dev.infra.keyring_source.keyring.get_password", return_value="my-secret"):
        assert source.get("svc", "key") == "my-secret"


def test_keyring_source_raises_on_missing_secret() -> None:
    source = KeyringSecretSource()
    with patch("adda_dev.infra.keyring_source.keyring.get_password", return_value=None):
        with pytest.raises(SecretError, match="No secret for"):
            source.get("svc", "key")


def test_keyring_source_wraps_no_keyring_error() -> None:
    source = KeyringSecretSource()
    with patch("adda_dev.infra.keyring_source.keyring.get_password", side_effect=NoKeyringError("no backend")):
        with pytest.raises(SecretError, match="Keyring unavailable"):
            source.get("svc", "key")


def test_keyring_source_wraps_generic_keyring_error() -> None:
    source = KeyringSecretSource()
    with patch("adda_dev.infra.keyring_source.keyring.get_password", side_effect=KeyringError("locked")):
        with pytest.raises(SecretError, match="Keyring unavailable"):
            source.get("svc", "key")
