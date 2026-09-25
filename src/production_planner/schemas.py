from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OutputRequest(BaseModel):
    item_key: str
    quantity: Decimal = Field(gt=0)
    priority: int = Field(default=1, ge=1)


class PlanRequest(BaseModel):
    outputs: list[OutputRequest] = Field(min_length=1)
    capacity_profile: str = "hay_day_default"
    station_overrides: dict[str, int] = Field(default_factory=dict)

    @field_validator("station_overrides")
    @classmethod
    def positive_capacities(cls, value: dict[str, int]) -> dict[str, int]:
        if any(count < 1 for count in value.values()):
            raise ValueError("station override counts must be at least 1")
        return value


class UserDataSessionRequest(BaseModel):
    use_last: bool = False


class UserDataSaveRequest(BaseModel):
    station_counts: dict[str, int] = Field(default_factory=dict)

    @field_validator("station_counts")
    @classmethod
    def positive_station_counts(cls, value: dict[str, int]) -> dict[str, int]:
        if any(not key or count < 1 for key, count in value.items()):
            raise ValueError("station counts require nonblank keys and values of at least 1")
        return value


class PlanDocument(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str
    engine_version: str
    generated_at: str
    source_database: dict[str, str]
    request: dict[str, Any]
    capacities: dict[str, int]
    bom: list[dict[str, Any]]
    production: list[dict[str, Any]]
    outputs: list[dict[str, Any]]
    jobs: list[dict[str, Any]]
    station_summary: list[dict[str, Any]]
    overall_completion_seconds: int
    actual_input_cost: str | None
    warnings: list[str]
