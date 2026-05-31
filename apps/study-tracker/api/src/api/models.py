"""Pydantic models for the Study Tracker API."""

from datetime import datetime
from typing import Dict

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StudySessionCreate(BaseModel):
    """Model for creating a new study session."""

    model_config = ConfigDict(extra="forbid")

    minutes: int = Field(
        ...,
        gt=0,
        le=1440,
        description="Study duration in minutes (1-1440, i.e. up to 24h)",
        examples=[30],
    )
    tag: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Tag for the study session (e.g., certification name, topic). "
        "Stored lowercased and stripped.",
        examples=["aws"],
    )

    @field_validator("tag")
    @classmethod
    def _normalize_tag(cls, v: str) -> str:
        """Strip whitespace and lowercase. Reject empty-after-strip."""
        normalized = v.strip().lower()
        if not normalized:
            raise ValueError("tag cannot be empty or whitespace-only")
        return normalized


class StudySession(StudySessionCreate):
    """Complete study session model including generated fields."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        ...,
        description="Unique identifier for the session",
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    )
    timestamp: datetime = Field(
        ...,
        description="UTC timestamp of when the session was created",
        examples=["2026-05-30T22:55:39.329000+00:00"],
    )


class Stats(BaseModel):
    """Model for aggregated statistics."""

    model_config = ConfigDict(extra="forbid")

    total_time: int = Field(..., description="Total study time in minutes", examples=[120])
    time_by_tag: Dict[str, int] = Field(
        ..., description="Study time grouped by tag", examples=[{"aws": 90, "kubernetes": 30}]
    )
    total_sessions: int = Field(..., description="Total number of study sessions", examples=[4])
    sessions_by_tag: Dict[str, int] = Field(
        ..., description="Number of sessions grouped by tag", examples=[{"aws": 3, "kubernetes": 1}]
    )
