from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, SmallInteger, String, func
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class BankAccount(Base):
    """Configuração por conta — item 21 do escopo original: cada conta pode
    ter tolerâncias e regras próprias."""
    __tablename__ = "bank_accounts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), nullable=False)

    bank: Mapped[str] = mapped_column(String(100), nullable=False)          # ex: 'Itaú'
    agency: Mapped[str | None] = mapped_column(String(20))
    account_number: Mapped[str] = mapped_column(String(30), nullable=False)  # ex: '98967-1'

    # Configurações — defaults refletem o que foi observado/validado nos
    # dados reais de janeiro/2026; ajustáveis por conta.
    date_tolerance_business_days: Mapped[int] = mapped_column(SmallInteger, default=2)
    amount_tolerance: Mapped[float] = mapped_column(Numeric(10, 2), default=0.01)
    consider_interest: Mapped[bool] = mapped_column(Boolean, default=True)
    consider_fee_in_settlement: Mapped[bool] = mapped_column(Boolean, default=False)
    period_cutoff_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    separate_anticipations: Mapped[bool] = mapped_column(Boolean, default=True)
    grouping_enabled: Mapped[bool] = mapped_column(Boolean, default=False)  # Regra 10/11 ainda não implementada

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    client: Mapped["Client"] = relationship(back_populates="bank_accounts")
