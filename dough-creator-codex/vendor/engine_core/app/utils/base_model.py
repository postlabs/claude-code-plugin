"""Shared Pydantic base models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AppBaseModel(BaseModel):
    """Base model with consistent Pydantic configuration."""

    model_config = ConfigDict(extra="ignore")


class ProviderModel(AppBaseModel):
    """Base model for provider-specific API responses.

    Tolerates unknown fields from external APIs and allows
    both camelCase aliases and snake_case field names.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)
