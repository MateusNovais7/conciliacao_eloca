from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, String
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class PedidoNotaFiscal(Base):
    """Persistência do FTP021A1 (Pedidos/Notas Fiscais) — complementa o
    FTP050 na recuperação de documentos apagados com o campo
    Representante (ver app/services/recovery_service.py)."""
    __tablename__ = "pedidos_notas_fiscais"
    __table_args__ = (
        Index("ix_pedido_nf_matching", "nota_fiscal", "bank_account_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    import_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_files.id"), nullable=False)
    bank_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_accounts.id"), nullable=False)

    local: Mapped[str] = mapped_column(String(100), nullable=False)
    pedido: Mapped[str | None] = mapped_column(String(30))
    nota_fiscal: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    serie: Mapped[str | None] = mapped_column(String(10))
    data_emissao: Mapped[date | None] = mapped_column(Date)
    cliente_id: Mapped[str | None] = mapped_column(String(30))
    razao_social: Mapped[str | None] = mapped_column(String(255))
    representante_id: Mapped[str | None] = mapped_column(String(30))
    representante_nome: Mapped[str | None] = mapped_column(String(255))

    import_file: Mapped["ImportFile"] = relationship()
