from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import require_api_key
from app.database.deps import get_session
from app.models.bank_account import BankAccount
from app.models.client import Client
from app.schemas.client import BankAccountCreate, BankAccountOut

router = APIRouter(prefix="/contas", tags=["contas"])


@router.post("", response_model=BankAccountOut, status_code=201)
def create_bank_account(payload: BankAccountCreate, session: Session = Depends(get_session), _=Depends(require_api_key)):
    client = session.get(Client, payload.client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    account = BankAccount(**payload.model_dump())
    session.add(account)
    session.flush()
    return account


@router.get("", response_model=list[BankAccountOut])
def list_bank_accounts(
    client_id: UUID | None = None,
    session: Session = Depends(get_session),
    _=Depends(require_api_key),
):
    query = session.query(BankAccount)
    if client_id:
        query = query.filter_by(client_id=client_id)
    return query.all()


@router.get("/{account_id}", response_model=BankAccountOut)
def get_bank_account(account_id: UUID, session: Session = Depends(get_session), _=Depends(require_api_key)):
    account = session.get(BankAccount, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")
    return account


@router.patch("/{account_id}", response_model=BankAccountOut)
def update_bank_account_config(
    account_id: UUID,
    payload: BankAccountCreate,
    session: Session = Depends(get_session),
    _=Depends(require_api_key),
):
    """Item 21 — atualiza as tolerâncias/regras da conta."""
    account = session.get(BankAccount, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")
    for field, value in payload.model_dump(exclude={"client_id"}).items():
        setattr(account, field, value)
    session.flush()
    return account
