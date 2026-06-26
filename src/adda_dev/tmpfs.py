"""
Tmpfs scratch-sizing value objects.
"""

from typing import Annotated

from pydantic import Field, field_validator

from .common import StrictModel

# Pattern for a valid size string: digits optionally followed by a single unit char.
_SIZE_PATTERN = r"^\d+[bkmgBKMG]?$"


class TmpfsSizes(StrictModel):
    """Fully-resolved tmpfs mount sizes; all fields are required."""

    home: Annotated[str, Field(pattern=_SIZE_PATTERN)] = "512m"
    workspace: Annotated[str, Field(pattern=_SIZE_PATTERN)] = "256m"
    tmp: Annotated[str, Field(pattern=_SIZE_PATTERN)] = "256m"


class TmpfsOverride(StrictModel):
    """Sparse patch of tmpfs sizes; None means inherit from project defaults."""

    home: str | None = None
    workspace: str | None = None
    tmp: str | None = None

    @field_validator("home", "workspace", "tmp", mode="before")
    @classmethod
    def _validate_size(cls, v: object) -> object:
        import re

        if v is not None and not re.match(_SIZE_PATTERN, str(v)):
            raise ValueError(f"Invalid size value {v!r}: must match {_SIZE_PATTERN}")
        return v
