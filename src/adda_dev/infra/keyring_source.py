"""
KeyringSecretSource: OS keyring adapter for the SecretSource port.
"""

import keyring
from keyring.errors import KeyringError

from ..domain.credentials import SecretError, SecretSource


class KeyringSecretSource(SecretSource):
    """SecretSource backed by the host OS keyring (via the keyring library)."""

    def get(self, service: str, key: str) -> str:
        """Look up service/key in the OS keyring; raise SecretError if not found."""
        try:
            value = keyring.get_password(service, key)
        except KeyringError as exc:
            raise SecretError(f"Keyring unavailable for {service!r}/{key!r}: {exc}") from exc
        if value is None:
            raise SecretError(f"No secret for {service!r}/{key!r}")
        return value
