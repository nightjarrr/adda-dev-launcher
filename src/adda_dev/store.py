"""
On-disk config store: file locations, name validation, and TOML load/validate.
"""

import os
import re
from pathlib import Path

import tomlkit
import tomlkit.exceptions
from pydantic import BaseModel, ValidationError

from .common import AddaDevError

# Valid project name: only safe filesystem characters, no path separators.
_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
# Dot-only names (. and ..) are path traversal risks even if they match the safe-chars regex.
_DOT_ONLY_RE = re.compile(r"^\.*$")


class TomlParseError(AddaDevError):
    """Raised when a TOML file cannot be parsed."""


class SchemaValidationError(AddaDevError):
    """Raised when a parsed TOML document fails Pydantic schema validation."""


class InvalidProjectNameError(AddaDevError):
    """Raised when a project name contains unsafe characters or path components."""


def resolve_config_dir() -> Path:
    """Return the adda-dev config directory, honouring $XDG_CONFIG_HOME."""
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "adda-dev"


def app_config_file(config_dir: Path) -> Path:
    """Return the path to config.toml inside config_dir."""
    return config_dir / "config.toml"


def projects_dir(config_dir: Path) -> Path:
    """Return the projects registry directory inside config_dir."""
    return config_dir / "projects"


def project_file(config_dir: Path, name: str) -> Path:
    """Return the path to the project TOML file, validating name first."""
    if not name or _DOT_ONLY_RE.match(name) or not _NAME_RE.match(name):
        raise InvalidProjectNameError(
            f"Invalid project name {name!r}: must match ^[A-Za-z0-9._-]+$, not be empty, and not be a dot-path."
        )
    return projects_dir(config_dir) / f"{name}.toml"


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
