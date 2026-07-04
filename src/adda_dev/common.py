"""
Cross-cutting foundations: root exception, shared Pydantic base model, and Output port.
"""

from types import TracebackType
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict


class AddaDevError(Exception):
    """Root exception for all adda-dev domain errors."""


class StrictModel(BaseModel):
    """Shared Pydantic base model with extra='forbid' applied to all subclasses."""

    model_config = ConfigDict(extra="forbid")


class StepContext:
    """Context manager returned by Output.step(); signals completion or failure of a named step."""

    def __enter__(self) -> StepContext:
        raise NotImplementedError

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        raise NotImplementedError

    def done(self, detail: str) -> None:
        raise NotImplementedError


class Output(Protocol):
    """Port for emitting user-visible messages without coupling to a delivery library."""

    def info(self, message: str) -> None: ...

    def warning(self, message: str) -> None: ...

    def error(self, exc: Exception) -> None: ...

    def ruler(self, title: str = "", *, pad: bool = True) -> None: ...

    def blank(self) -> None: ...

    def kv(self, key: str, value: str | tuple[str, ...]) -> None: ...

    def step(self, label: str) -> StepContext: ...
