from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Numeric, String, Text
from sqlalchemy import JSON
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class BankTransaction(Base):
    """Camada 'dados normalizados' (item 6/8 do escopo) — não é o arquivo
    original (isso é ImportFile), é o resultado já estruturado do
    importador, pronto para o motor de matching. `raw_data` preserva as
    linhas originais agrupadas para auditoria."""
    __tablename__ = "bank_transactions"
    __table_args__ = (
        Index("ix_bank_tx_matching", "normalized_title", "movement_date", "bank_account_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    import_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_files.id"), nullable=False)
    bank_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_accounts.id"), nullable=False)

    bank: Mapped[str] = mapped_column(String(100))
    movement_date: Mapped[date] = mapped_column(Date, nullable=False)
    nosso_numero: Mapped[str] = mapped_column(String(50), nullable=False)
    seu_numero: Mapped[str | None] = mapped_column(String(50))
    normalized_title: Mapped[str | None] = mapped_column(String(50), index=True)
    payer_name: Mapped[str | None] = mapped_column(String(255))
    operation_type: Mapped[str | None] = mapped_column(String(100))

    principal_amount: Mapped[float | None] = mapped_column(Numeric(14, 2))
    fee_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    interest_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    final_amount: Mapped[float | None] = mapped_column(Numeric(14, 2))

    source_sheet: Mapped[str | None] = mapped_column(String(50))
    raw_data: Mapped[dict | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)

    import_file: Mapped["ImportFile"] = relationship()

    @property
    def client_amount(self) -> float | None:
        if self.principal_amount is None:
            return None
        return round(float(self.principal_amount) + float(self.interest_amount), 2)
