from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, SmallInteger, String, Text, func
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base

# Os valores possíveis espelham app.reconciliation.engine.ReconciliationStatus
# (mantido como string simples, não Enum de banco, para não exigir
# migration toda vez que uma nova categoria do motor for adicionada — ver
# item 11 do escopo: "nunca salve apenas texto solto como status", por isso
# a validação do valor permitido fica na camada de serviço/schema Pydantic,
# não solta no banco).


class ReconciliationMatchRow(Base):
    __tablename__ = "reconciliation_matches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    reconciliation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reconciliations.id"), nullable=False)

    bank_transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bank_transactions.id"))
    erp_transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("erp_transactions.id"))
    documento_recebido_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documentos_recebidos.id"))

    status: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    confidence: Mapped[int] = mapped_column(SmallInteger, default=0)
    diagnostic: Mapped[str | None] = mapped_column(Text)

    is_manual_override: Mapped[bool] = mapped_column(Boolean, default=False)
    ignored: Mapped[bool] = mapped_column(Boolean, default=False)  # status 'IGNORADO' do item 11

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    reconciliation: Mapped["Reconciliation"] = relationship(back_populates="matches")
    bank_transaction: Mapped["BankTransaction | None"] = relationship()
    erp_transaction: Mapped["ERPTransaction | None"] = relationship()
    documento_recebido: Mapped["DocumentoRecebido | None"] = relationship()
