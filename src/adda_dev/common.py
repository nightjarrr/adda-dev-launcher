"""
Cross-cutting foundations: root exception, shared Pydantic base model, and Output port.
"""

from typing import Protocol

from pydantic import BaseModel, ConfigDict


class AddaDevError(Exception):
    """Root exception for all adda-dev domain errors."""


class StrictModel(BaseModel):
    """Shared Pydantic base model with extra='forbid' applied to all subclasses."""

    model_config = ConfigDict(extra="forbid")


class Output(Protocol):
    """Port for emitting user-visible messages without coupling to a delivery library."""

    def info(self, message: str) -> None: ...

    def warning(self, message: str) -> None: ...

    def error(self, exc: Exception) -> None: ...
