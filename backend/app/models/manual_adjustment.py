from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class ManualAdjustmentReason(str, enum.Enum):
    """Item 18 do escopo — motivos pré-definidos para conciliação manual."""
    NUMERACAO_DIFERENTE = "NUMERACAO_DIFERENTE"
    DIFERENCA_DE_DATA = "DIFERENCA_DE_DATA"
    AGRUPAMENTO = "AGRUPAMENTO"
    AJUSTE_CONTABIL = "AJUSTE_CONTABIL"
    CLASSIFICACAO = "CLASSIFICACAO"
    OUTRO = "OUTRO"


class ManualAdjustment(Base):
    __tablename__ = "manual_adjustments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    reconciliation_match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reconciliation_matches.id"), nullable=False,
    )

    reason: Mapped[ManualAdjustmentReason] = mapped_column(
        Enum(ManualAdjustmentReason, name="manual_adjustment_reason"), nullable=False,
    )
    observation: Mapped[str | None] = mapped_column(Text)

    previous_status: Mapped[str] = mapped_column(String(60), nullable=False)
    new_status: Mapped[str] = mapped_column(String(60), nullable=False)

    performed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    match: Mapped["ReconciliationMatchRow"] = relationship()
