"""Shared Pydantic base models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AppBaseModel(BaseModel):
    """Base model with consistent Pydantic configuration."""

    model_config = ConfigDict(extra="ignore")
