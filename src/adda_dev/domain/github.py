"""
GitHub identity domain model.
"""

from dataclasses import dataclass
from typing import ClassVar

from .credentials import Secret, SecretSource


@dataclass(frozen=True)
class GitHub(Secret):
    """GitHub identity and credential retrieval domain model."""

    _service: ClassVar[str] = "adda-dev:github"

    owner: str
    repo: str
    secret_name: str
    source: SecretSource
