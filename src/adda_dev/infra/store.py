"""
On-disk config store: file locations, name validation, and TOML load/validate.
"""

import os
import re
from pathlib import Path

import tomlkit
import tomlkit.exceptions
from pydantic import BaseModel, ValidationError

from ..common import AddaDevError

# Valid registry slug: letters, digits, hyphens, underscores only — no dots or path separators.
_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class TomlParseError(AddaDevError):
    """Raised when a TOML file cannot be parsed."""


class SchemaValidationError(AddaDevError):
    """Raised when a parsed TOML document fails Pydantic schema validation."""


class InvalidFileNameError(AddaDevError):
    """Raised when a name contains unsafe characters or is otherwise not a valid registry slug."""


def resolve_config_dir() -> Path:
    """Return the adda-dev config directory, honouring $XDG_CONFIG_HOME."""
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "adda-dev"


def validate_file_name(name: str) -> str:
    """Validate that name is a safe registry slug and return it unchanged.

    Raises:
        InvalidFileNameError: if name is empty, contains dots, path separators, or any
            character outside [A-Za-z0-9_-].
    """
    if not name or not _NAME_RE.match(name):
        raise InvalidFileNameError(
            f"Invalid name {name!r}: must be non-empty and match ^[A-Za-z0-9_-]+$ (no dots or path separators)."
        )
    return name


def load_toml[T: BaseModel](path: Path, model: type[T]) -> T:
    """Parse a TOML file and validate it against a Pydantic model.

    Raises:
        TomlParseError: if the file contains invalid TOML syntax.
        SchemaValidationError: if the parsed data fails model validation.
    """
    try:
        raw = tomlkit.parse(path.read_text()).unwrap()
    except tomlkit.exceptions.TOMLKitError as exc:
        raise TomlParseError(f"Failed to parse TOML file {path}: {exc}") from exc

    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise SchemaValidationError(f"Schema validation failed for {path}: {exc}") from exc
