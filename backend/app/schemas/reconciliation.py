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
    crp032a1_import_file_id: UUID | None = None


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


class ReconciliationHistoryItem(BaseModel):
    id: UUID
    competencia_year: int
    competencia_month: int
    status: str
    reconciled_pct: float
    created_at: datetime
    closed_at: datetime | None


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


class DocumentoRecebidoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    documento: str
    cliente: str | None
    data_pagamento: date | None
    valor_emissao: float | None
    valor_desconto: float
    valor_abatimento: float
    valor_juros: float
    valor_multa: float
    valor_pago: float | None


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
    documento_recebido: DocumentoRecebidoOut | None


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


class RecoveredTitleOut(BaseModel):
    match_id: UUID
    seu_numero: str
    nosso_numero: str
    nota_fiscal: str
    sequencia: str
    payer_name: str | None
    principal_amount: float | None
    due_date: date | None
    movement_date: date
    agency: str | None
    local_id: int | None
    local_nome: str | None
    cliente_id: str | None
    razao_social: str | None
    data_emissao: date | None
    representante_id: str | None
    representante_nome: str | None
    resolved: bool

