from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session
from uuid import UUID

from app.api.auth import require_api_key
from app.database.deps import get_session
from app.models.bank_account import BankAccount
from app.models.import_file import ImportFile
from app.schemas.reconciliation import ImportFileOut
from app.services.import_service import (
    import_bank_file,
    import_crp032a1_file,
    import_erp_file,
    import_ftp021a1_file,
    import_ftp050_file,
)

router = APIRouter(prefix="/importacoes", tags=["importacoes"])


@router.get("", response_model=list[ImportFileOut])
def list_import_files(
    bank_account_id: UUID | None = None,
    session: Session = Depends(get_session),
    _=Depends(require_api_key),
):
    """Lista os arquivos já importados — útil para retomar uma conciliação
    sem reimportar um arquivo que já foi processado com sucesso (ver
    DuplicateImportError, item 33 do escopo: idempotência por hash)."""
    query = session.query(ImportFile).order_by(ImportFile.imported_at.desc())
    if bank_account_id:
        query = query.filter_by(bank_account_id=bank_account_id)
    return query.all()


def _storage_dir() -> Path:
    import os
    base = Path(os.environ.get("UPLOAD_DIR", "storage/uploads"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def _save_upload(upload: UploadFile) -> Path:
    dest = _storage_dir() / f"{uuid.uuid4()}_{upload.filename}"
    with dest.open("wb") as f:
        shutil.copyfileobj(upload.file, f)
    return dest


@router.post("/erp", response_model=ImportFileOut, status_code=201)
def upload_erp_file(
    response: Response,
    bank_account_id: UUID = Form(...),
    competencia_year: int = Form(...),
    competencia_month: int = Form(...),
    imported_by: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _=Depends(require_api_key),
):
    account = session.get(BankAccount, bank_account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")

    saved_path = _save_upload(file)
    try:
        import_file, reused = import_erp_file(
            session, bank_account_id, saved_path,
            competencia_year, competencia_month, imported_by,
            storage_path=str(saved_path),
        )
    except Exception as e:
        # Item 34: nunca expor stack trace ao usuário final. O erro técnico
        # completo continua disponível nos logs do servidor.
        raise HTTPException(
            status_code=422,
            detail=(
                "Não foi possível processar o arquivo do ERP. Verifique se o "
                "arquivo corresponde ao modelo esperado (relatório FFP045A2)."
            ),
        ) from e
    if reused:
        response.status_code = 200  # nada novo foi criado, reaproveitamos o import existente
    return import_file


@router.post("/banco", response_model=ImportFileOut, status_code=201)
def upload_bank_file(
    response: Response,
    bank_account_id: UUID = Form(...),
    competencia_year: int = Form(...),
    competencia_month: int = Form(...),
    imported_by: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _=Depends(require_api_key),
):
    account = session.get(BankAccount, bank_account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")

    saved_path = _save_upload(file)
    try:
        import_file, reused = import_bank_file(
            session, bank_account_id, saved_path,
            competencia_year, competencia_month, imported_by,
            storage_path=str(saved_path),
        )
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=(
                "Não foi possível processar o arquivo do banco. Verifique se o "
                "arquivo corresponde ao modelo esperado (Francesinha/extrato de cobrança)."
            ),
        ) from e
    if reused:
        response.status_code = 200
    return import_file


@router.post("/crp032a1", response_model=ImportFileOut, status_code=201)
def upload_crp032a1_file(
    response: Response,
    bank_account_id: UUID = Form(...),
    competencia_year: int = Form(...),
    competencia_month: int = Form(...),
    imported_by: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _=Depends(require_api_key),
):
    """CRP032A1 (Relação de Documentos Recebidos) — fonte OPCIONAL, usada
    só para explicar desconto comercial em valores divergentes (Regra 12).
    Nem toda conciliação precisa desse arquivo."""
    account = session.get(BankAccount, bank_account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")

    saved_path = _save_upload(file)
    try:
        import_file, reused = import_crp032a1_file(
            session, bank_account_id, saved_path,
            competencia_year, competencia_month, imported_by,
            storage_path=str(saved_path),
        )
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=(
                "Não foi possível processar o arquivo CRP032A1. Verifique se o "
                "arquivo corresponde ao modelo esperado (Relação de Documentos Recebidos)."
            ),
        ) from e
    if reused:
        response.status_code = 200
    return import_file


@router.post("/ftp050", response_model=ImportFileOut, status_code=201)
def upload_ftp050_file(
    response: Response,
    bank_account_id: UUID = Form(...),
    competencia_year: int = Form(...),
    competencia_month: int = Form(...),
    imported_by: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _=Depends(require_api_key),
):
    """FTP050 (Relação de NF Emitidas) — usado só para recuperar Local e
    Cliente de documentos apagados por engano (ver /conciliacoes/{id}/recuperacao).
    Pode ser enviado várias vezes (o ERP limita a 6 meses por exportação);
    cada arquivo soma ao acervo sem duplicar."""
    account = session.get(BankAccount, bank_account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")

    saved_path = _save_upload(file)
    try:
        import_file, reused = import_ftp050_file(
            session, bank_account_id, saved_path,
            competencia_year, competencia_month, imported_by,
            storage_path=str(saved_path),
        )
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=(
                "Não foi possível processar o arquivo FTP050. Verifique se o "
                "arquivo corresponde ao modelo esperado (Relação de NF Emitidas)."
            ),
        ) from e
    if reused:
        response.status_code = 200
    return import_file


@router.post("/ftp021a1", response_model=ImportFileOut, status_code=201)
def upload_ftp021a1_file(
    response: Response,
    bank_account_id: UUID = Form(...),
    competencia_year: int = Form(...),
    competencia_month: int = Form(...),
    imported_by: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _=Depends(require_api_key),
):
    """FTP021A1 (Pedidos/Notas Fiscais) — complementa o FTP050 na
    recuperação de documentos apagados com o campo Representante. Pode
    ser enviado várias vezes; cada arquivo soma ao acervo sem duplicar."""
    account = session.get(BankAccount, bank_account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")

    saved_path = _save_upload(file)
    try:
        import_file, reused = import_ftp021a1_file(
            session, bank_account_id, saved_path,
            competencia_year, competencia_month, imported_by,
            storage_path=str(saved_path),
        )
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=(
                "Não foi possível processar o arquivo FTP021A1. Verifique se o "
                "arquivo corresponde ao modelo esperado (Pedidos/Notas Fiscais)."
            ),
        ) from e
    if reused:
        response.status_code = 200
    return import_file
