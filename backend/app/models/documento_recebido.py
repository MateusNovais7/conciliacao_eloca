from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy import JSON
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class DocumentoRecebido(Base):
    """Persistência do CRP032A1 (Relação de Documentos Recebidos) — fonte
    OPCIONAL que explica desconto comercial em valores divergentes
    (Regra 12 do motor, ver app/reconciliation/engine.py)."""
    __tablename__ = "documentos_recebidos"
    __table_args__ = (
        Index("ix_documento_recebido_matching", "normalized_title", "bank_account_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    import_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_files.id"), nullable=False)
    bank_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_accounts.id"), nullable=False)

    documento: Mapped[str] = mapped_column(String(50), nullable=False)
    normalized_title: Mapped[str | None] = mapped_column(String(50), index=True)
    cliente: Mapped[str | None] = mapped_column(String(255))
    data_pagamento: Mapped[date | None] = mapped_column(Date)

    valor_emissao: Mapped[float | None] = mapped_column(Numeric(14, 2))
    impostos_retidos: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    valor_desconto: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    valor_abatimento: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    valor_juros: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    valor_multa: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    valor_pago: Mapped[float | None] = mapped_column(Numeric(14, 2))

    raw_data: Mapped[dict | None] = mapped_column(JSON)

    import_file: Mapped["ImportFile"] = relationship()

    @property
    def ajuste_liquido(self) -> float:
        return round(
            -float(self.impostos_retidos) - float(self.valor_desconto) - float(self.valor_abatimento)
            + float(self.valor_juros) + float(self.valor_multa),
            2,
        )
