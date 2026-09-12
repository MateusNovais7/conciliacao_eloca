from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, SmallInteger, String, func
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class ReconciliationLifecycleStatus(str, enum.Enum):
    """Item 20 do escopo — não confundir com o status por título
    (ReconciliationStatus do motor); este é o status da competência
    inteira."""
    RASCUNHO = "RASCUNHO"
    EM_ANALISE = "EM_ANALISE"
    CONCILIADA = "CONCILIADA"
    FECHADA = "FECHADA"
    REABERTA = "REABERTA"


class Reconciliation(Base):
    __tablename__ = "reconciliations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bank_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_accounts.id"), nullable=False)

    competencia_year: Mapped[int] = mapped_column(Integer, nullable=False)
    competencia_month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[ReconciliationLifecycleStatus] = mapped_column(
        default=ReconciliationLifecycleStatus.RASCUNHO,
    )

    erp_import_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("import_files.id"))
    bank_import_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("import_files.id"))
    crp032a1_import_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("import_files.id"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[str | None] = mapped_column(String(255))

    bank_account: Mapped["BankAccount"] = relationship()
    matches: Mapped[list["ReconciliationMatchRow"]] = relationship(back_populates="reconciliation")
