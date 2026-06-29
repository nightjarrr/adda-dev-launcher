"""
pytest configuration.
"""

from adda_dev.domain.credentials import SecretError, SecretSource


class FakeSecretSource(SecretSource):
    """SecretSource test double backed by a dict."""

    def __init__(self, secrets: dict[tuple[str, str], str] | None = None) -> None:
        self._secrets: dict[tuple[str, str], str] = secrets or {}

    def get(self, service: str, key: str) -> str:
        value = self._secrets.get((service, key))
        if value is None:
            raise SecretError(f"No secret for {service!r}/{key!r}")
        return value
