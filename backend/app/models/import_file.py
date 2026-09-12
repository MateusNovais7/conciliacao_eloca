from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class ImportFileKind(str, enum.Enum):
    ERP = "ERP"
    BANK = "BANK"
    CRP032A1 = "CRP032A1"
    FTP050 = "FTP050"


class ImportFile(Base):
    """Preserva metadados do arquivo original — item 6 do escopo: nunca
    alteramos o dado original, guardamos hash (idempotência, item 33),
    nome, data/hora, usuário, conta e competência."""
    __tablename__ = "import_files"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bank_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_accounts.id"), nullable=False)

    # 'kind' guarda o valor do ImportFileKind como texto simples, não um
    # Enum de banco — mesma decisão tomada para ReconciliationMatchRow.status:
    # evita precisar de uma migration (ALTER TYPE no Postgres) toda vez que
    # um novo tipo de arquivo aparecer (foi exatamente o caso do CRP032A1).
    # A validação de quais valores são aceitos fica na camada de
    # serviço/schema Pydantic.
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # sha256
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)

    competencia_year: Mapped[int] = mapped_column(Integer, nullable=False)
    competencia_month: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)

    row_count: Mapped[int | None] = mapped_column(Integer)
    imported_by: Mapped[str | None] = mapped_column(String(255))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    bank_account: Mapped["BankAccount"] = relationship()
