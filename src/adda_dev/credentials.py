"""
SecretStore protocol, KeyringSecretStore implementation, and Secret ABC.
"""

import abc
from typing import ClassVar, Protocol, runtime_checkable

import keyring

from .common import AddaDevError


class SecretError(AddaDevError):
    """Raised when no secret is found in the store."""


@runtime_checkable
class SecretStore(Protocol):
    """Contract for secret retrieval backends."""

    def get(self, service: str, key: str) -> str:
        """Return the secret for the given service and key, or raise SecretError."""
        ...


class KeyringSecretStore:
    """SecretStore backed by the host OS keyring (via the keyring library)."""

    def get(self, service: str, key: str) -> str:
        """Look up service/key in the OS keyring; raise SecretError if not found."""
        value = keyring.get_password(service, key)
        if value is None:
            raise SecretError(f"No secret for {service!r}/{key!r}")
        return value


class Secret(abc.ABC):
    """Base class for credential-bearing domain models.

    Subclasses are frozen dataclasses that own the ``secret_name`` and ``store``
    fields. Declaring the annotations here lets mypy accept ``self.secret_name``
    and ``self.store`` in the concrete ``get_secret`` method body.
    """

    _service: ClassVar[str]

    # Expected instance attributes — owned as dataclass fields by each subclass.
    secret_name: str
    store: SecretStore

    def get_secret(self) -> str:
        """Retrieve the secret from the store using this model's service namespace."""
        return self.store.get(self._service, self.secret_name)
