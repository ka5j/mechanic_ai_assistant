# core/config_schema.py

from pydantic import BaseModel, Field, field_validator, ValidationError
from typing import List, Optional
from pathlib import Path


class ServiceConfig(BaseModel):
    name: str
    duration_minutes: int = Field(30, gt=0)
    price: Optional[str] = None  # e.g., "$79.99"

    @field_validator("name")
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("service name must not be empty")
        return v.strip()


class BookingSlotsConfig(BaseModel):
    interval_minutes: int = Field(30, gt=0)


class HoursConfig(BaseModel):
    open: str = Field(..., pattern=r"^\d{2}:\d{2}$")  # "09:00"
    close: str = Field(..., pattern=r"^\d{2}:\d{2}$")  # "17:00"


class CalendarConfig(BaseModel):
    ics_path: Path

    def ensure_parent(self):
        self.ics_path.parent.mkdir(parents=True, exist_ok=True)


class RootConfig(BaseModel):
    shop_name: Optional[str] = "Mechanic Shop"
    services: List[ServiceConfig]
    booking_slots: BookingSlotsConfig = BookingSlotsConfig()
    hours: HoursConfig
    calendar: CalendarConfig

    @field_validator("services")
    def must_have_at_least_one_service(cls, v):
        if not v:
            raise ValueError("At least one service must be defined")
        return v
