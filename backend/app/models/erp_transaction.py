from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Numeric, String, Text
from sqlalchemy import JSON
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class ERPTransaction(Base):
    __tablename__ = "erp_transactions"
    __table_args__ = (
        Index("ix_erp_tx_matching", "normalized_title", "transaction_date", "bank_account_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    import_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_files.id"), nullable=False)
    bank_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_accounts.id"), nullable=False)

    account_local: Mapped[str | None] = mapped_column(String(100))
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    invoice_number_raw: Mapped[str | None] = mapped_column(String(50))
    normalized_title: Mapped[str | None] = mapped_column(String(50), index=True)
    tipo: Mapped[str | None] = mapped_column(String(50))
    tipo_documento: Mapped[str | None] = mapped_column(String(100))
    nota_fiscal: Mapped[str | None] = mapped_column(String(50))
    descricao: Mapped[str | None] = mapped_column(Text)

    incoming_amount: Mapped[float | None] = mapped_column(Numeric(14, 2))
    outgoing_amount: Mapped[float | None] = mapped_column(Numeric(14, 2))
    balance: Mapped[float | None] = mapped_column(Numeric(14, 2))

    is_anticipation: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_data: Mapped[dict | None] = mapped_column(JSON)

    import_file: Mapped["ImportFile"] = relationship()
