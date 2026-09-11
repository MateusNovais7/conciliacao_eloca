from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ImportFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    bank_account_id: UUID
    kind: str
    original_filename: str
    competencia_year: int
    competencia_month: int
    period_start: date | None
    period_end: date | None
    row_count: int | None
    imported_by: str | None
    imported_at: datetime


class ImportErrorOut(BaseModel):
    """Mensagem amigável para o usuário — item 24/34 do escopo: nunca
    stack trace Python na resposta da API."""
    message: str


class ReconciliationCreate(BaseModel):
    bank_account_id: UUID
    competencia_year: int
    competencia_month: int
    erp_import_file_id: UUID
    bank_import_file_id: UUID


class ReconciliationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    bank_account_id: UUID
    competencia_year: int
    competencia_month: int
    status: str
    created_at: datetime
    closed_at: datetime | None
    closed_by: str | None


class DashboardStatusCount(BaseModel):
    status: str
    count: int
    total_amount: float


class DashboardOut(BaseModel):
    reconciliation_id: UUID
    bank_titles_count: int
    erp_titles_count: int
    reconciled_count: int
    reconciled_pct: float
    reconciled_amount: float
    divergent_amount: float
    by_status: list[DashboardStatusCount]


class ReconciliationMatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: str
    confidence: int
    diagnostic: str | None
    bank_transaction_id: UUID | None
    erp_transaction_id: UUID | None
    is_manual_override: bool
    ignored: bool


class BankTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    movement_date: date
    seu_numero: str | None
    nosso_numero: str
    payer_name: str | None
    operation_type: str | None
    principal_amount: float | None
    interest_amount: float
    fee_amount: float
    final_amount: float | None


class ERPTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    transaction_date: date
    invoice_number_raw: str | None
    nota_fiscal: str | None
    descricao: str | None
    incoming_amount: float | None
    outgoing_amount: float | None


class ReconciliationMatchDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: str
    confidence: int
    diagnostic: str | None
    is_manual_override: bool
    ignored: bool
    bank_transaction: BankTransactionOut | None
    erp_transaction: ERPTransactionOut | None


class ManualAdjustmentCreate(BaseModel):
    reason: str  # ver ManualAdjustmentReason
    observation: str | None = None
    new_status: str
    performed_by: str


class DailyReconciliationRow(BaseModel):
    date: date
    bank_total: float
    erp_total: float
    difference: float
    status: str  # "OK" | "DIVERGENTE"
    match_ids: list[UUID]

