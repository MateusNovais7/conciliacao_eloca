from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ClientCreate(BaseModel):
    name: str


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    created_at: datetime


class BankAccountCreate(BaseModel):
    client_id: UUID
    bank: str
    agency: str | None = None
    account_number: str
    date_tolerance_business_days: int = 2
    amount_tolerance: float = 0.01
    consider_interest: bool = True
    consider_fee_in_settlement: bool = False
    period_cutoff_enabled: bool = True
    separate_anticipations: bool = True
    grouping_enabled: bool = False


class BankAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    client_id: UUID
    bank: str
    agency: str | None
    account_number: str
    date_tolerance_business_days: int
    amount_tolerance: float
    consider_interest: bool
    consider_fee_in_settlement: bool
    period_cutoff_enabled: bool
    separate_anticipations: bool
    grouping_enabled: bool
