from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import require_api_key
from app.database.deps import get_session
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientOut

router = APIRouter(prefix="/clientes", tags=["clientes"])


@router.post("", response_model=ClientOut, status_code=201)
def create_client(payload: ClientCreate, session: Session = Depends(get_session), _=Depends(require_api_key)):
    existing = session.query(Client).filter_by(name=payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Já existe um cliente chamado '{payload.name}'.")
    client = Client(name=payload.name)
    session.add(client)
    session.flush()
    return client


@router.get("", response_model=list[ClientOut])
def list_clients(session: Session = Depends(get_session), _=Depends(require_api_key)):
    return session.query(Client).order_by(Client.name).all()


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: UUID, session: Session = Depends(get_session), _=Depends(require_api_key)):
    client = session.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    return client
