from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy import JSON
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class AuditAction(str, enum.Enum):
    IMPORTACAO = "IMPORTACAO"
    CONCILIACAO = "CONCILIACAO"
    ALTERACAO = "ALTERACAO"
    AJUSTE_MANUAL = "AJUSTE_MANUAL"
    IGNORADO = "IGNORADO"
    REABERTURA = "REABERTURA"
    EXPORTACAO = "EXPORTACAO"
    EXCLUSAO = "EXCLUSAO"
    FECHAMENTO = "FECHAMENTO"


class AuditLog(Base):
    """Item 19 do escopo — toda ação importante gera log com usuário,
    data/hora, ação, estado antes/depois e contexto."""
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction, name="audit_action"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)  # ex: 'ReconciliationMatch'
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)

    performed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    context: Mapped[dict | None] = mapped_column(JSON)
