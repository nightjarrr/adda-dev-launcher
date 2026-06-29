"""
KeyringSecretSource: OS keyring adapter for the SecretSource port.
"""

import keyring

from ..domain.credentials import SecretError, SecretSource


class KeyringSecretSource(SecretSource):
    """SecretSource backed by the host OS keyring (via the keyring library)."""

    def get(self, service: str, key: str) -> str:
        """Look up service/key in the OS keyring; raise SecretError if not found."""
        value = keyring.get_password(service, key)
        if value is None:
            raise SecretError(f"No secret for {service!r}/{key!r}")
        return value
