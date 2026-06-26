"""
Cross-cutting foundations: root exception and shared Pydantic base model.
"""

from pydantic import BaseModel, ConfigDict


class AddaDevError(Exception):
    """Root exception for all adda-dev domain errors."""


class StrictModel(BaseModel):
    """Shared Pydantic base model with extra='forbid' applied to all subclasses."""

    model_config = ConfigDict(extra="forbid")
