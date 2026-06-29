"""
SecretSource protocol, Secret ABC, and SecretError.
"""

import abc
from typing import ClassVar

from ..common import AddaDevError


class SecretError(AddaDevError):
    """Raised when no secret is found in the source."""


class SecretSource(abc.ABC):
    """Abstract base for secret retrieval backends."""

    @abc.abstractmethod
    def get(self, service: str, key: str) -> str:
        """Return the secret for the given service and key, or raise SecretError."""


class Secret(abc.ABC):
    """Base class for credential-bearing domain models.

    Subclasses are frozen dataclasses that own the ``secret_name`` and ``source``
    fields. Declaring the annotations here lets mypy accept ``self.secret_name``
    and ``self.source`` in the concrete ``get_secret`` method body.
    """

    _service: ClassVar[str]

    # Expected instance attributes — owned as dataclass fields by each subclass.
    secret_name: str
    source: SecretSource

    def get_secret(self) -> str:
        """Retrieve the secret from the source using this model's service namespace."""
        return self.source.get(self._service, self.secret_name)
