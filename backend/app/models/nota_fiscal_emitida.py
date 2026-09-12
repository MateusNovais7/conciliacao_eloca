from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class NotaFiscalEmitida(Base):
    """Persistência do FTP050 (Relação de NF Emitidas) — usado só para
    recuperar Local/Cliente de documentos apagados por engano (ver
    app/services/recovery_service.py). Não participa do motor de
    conciliação normal."""
    __tablename__ = "notas_fiscais_emitidas"
    __table_args__ = (
        Index("ix_nf_emitida_matching", "nota_fiscal", "bank_account_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    import_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_files.id"), nullable=False)
    bank_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_accounts.id"), nullable=False)

    local_nome: Mapped[str] = mapped_column(String(100), nullable=False)
    local_id: Mapped[int | None] = mapped_column()
    data_emissao: Mapped[date | None] = mapped_column(Date)
    nota_fiscal: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    cliente_id: Mapped[str | None] = mapped_column(String(30))
    razao_social: Mapped[str | None] = mapped_column(String(255))
    cnpj_cpf: Mapped[str | None] = mapped_column(String(20))
    total: Mapped[float | None] = mapped_column(Numeric(14, 2))

    import_file: Mapped["ImportFile"] = relationship()
