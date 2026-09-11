"""
Serviço de importação — liga os importadores (app/importers) à
persistência. Responsável por:
  - checar idempotência por hash antes de duplicar um import (item 33);
  - gravar ImportFile com os metadados exigidos (item 6);
  - persistir BankTransaction / ERPTransaction normalizados.

Não decide política de negócio (isso é do motor); só materializa o que os
importadores já calcularam.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.importers.banks.itau_francesinha import import_itau_francesinha
from app.importers.erp.ffp045a2 import import_erp_ffp045a2
from app.models.bank_account import BankAccount
from app.models.bank_transaction import BankTransaction as BankTransactionRow
from app.models.erp_transaction import ERPTransaction as ERPTransactionRow
from app.models.import_file import ImportFile, ImportFileKind


class DuplicateImportError(Exception):
    """Levantado quando o mesmo arquivo (mesmo hash) já foi importado para
    esta conta — item 33: nunca duplicar lançamentos silenciosamente."""
    def __init__(self, existing_import_file_id: UUID):
        self.existing_import_file_id = existing_import_file_id
        super().__init__(
            f"Este arquivo já foi importado anteriormente (ImportFile {existing_import_file_id})."
        )


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_idempotent(session: Session, bank_account_id: UUID, file_hash: str) -> None:
    existing = (
        session.query(ImportFile)
        .filter_by(bank_account_id=bank_account_id, file_hash=file_hash)
        .first()
    )
    if existing:
        raise DuplicateImportError(existing.id)


def import_erp_file(
    session: Session,
    bank_account_id: UUID,
    file_path: str | Path,
    competencia_year: int,
    competencia_month: int,
    imported_by: str,
    storage_path: str,
) -> ImportFile:
    file_path = Path(file_path)
    file_hash = _file_hash(file_path)
    _check_idempotent(session, bank_account_id, file_hash)

    transactions = import_erp_ffp045a2(file_path)

    dates = [t.transaction_date for t in transactions if t.transaction_date]
    import_file = ImportFile(
        bank_account_id=bank_account_id,
        kind=ImportFileKind.ERP,
        original_filename=file_path.name,
        file_hash=file_hash,
        storage_path=storage_path,
        competencia_year=competencia_year,
        competencia_month=competencia_month,
        period_start=min(dates) if dates else None,
        period_end=max(dates) if dates else None,
        row_count=len(transactions),
        imported_by=imported_by,
    )
    session.add(import_file)
    session.flush()  # garante import_file.id antes de criar as linhas filhas

    for t in transactions:
        session.add(ERPTransactionRow(
            import_file_id=import_file.id,
            bank_account_id=bank_account_id,
            account_local=t.account_local,
            transaction_date=t.transaction_date,
            invoice_number_raw=t.invoice_number_raw,
            normalized_title=t.normalized_title,
            tipo=t.tipo,
            tipo_documento=t.tipo_documento,
            nota_fiscal=t.nota_fiscal,
            descricao=t.descricao,
            incoming_amount=t.incoming_amount,
            outgoing_amount=t.outgoing_amount,
            balance=t.balance,
            is_anticipation=t.is_anticipation,
            raw_data={k: str(v) for k, v in t.raw_row.items()},
        ))

    # Commit explícito: não dependemos do timing do ciclo de vida da
    # dependência do FastAPI (get_session) para garantir que o ImportFile
    # e suas transações estejam de fato visíveis a outras requisições antes
    # de devolvermos a resposta HTTP ao cliente. Sem isso, uma corrida real
    # aconteceu em produção: o frontend recebia o 201 com o ID do arquivo e
    # já disparava a próxima chamada (criar a conciliação) antes do commit
    # ter sido confirmado no Postgres, gerando ForeignKeyViolation.
    session.commit()
    return import_file


def import_bank_file(
    session: Session,
    bank_account_id: UUID,
    file_path: str | Path,
    competencia_year: int,
    competencia_month: int,
    imported_by: str,
    storage_path: str,
) -> ImportFile:
    file_path = Path(file_path)
    file_hash = _file_hash(file_path)
    _check_idempotent(session, bank_account_id, file_hash)

    bank_account = session.get(BankAccount, bank_account_id)
    transactions = import_itau_francesinha(file_path, bank=bank_account.bank if bank_account else "Itaú")

    dates = [t.movement_date for t in transactions]
    import_file = ImportFile(
        bank_account_id=bank_account_id,
        kind=ImportFileKind.BANK,
        original_filename=file_path.name,
        file_hash=file_hash,
        storage_path=storage_path,
        competencia_year=competencia_year,
        competencia_month=competencia_month,
        period_start=min(dates) if dates else None,
        period_end=max(dates) if dates else None,
        row_count=len(transactions),
        imported_by=imported_by,
    )
    session.add(import_file)
    session.flush()

    for t in transactions:
        session.add(BankTransactionRow(
            import_file_id=import_file.id,
            bank_account_id=bank_account_id,
            bank=t.bank,
            movement_date=t.movement_date,
            nosso_numero=t.nosso_numero,
            seu_numero=t.seu_numero,
            normalized_title=t.normalized_title,
            payer_name=t.payer_name,
            operation_type=t.operation_type,
            principal_amount=t.principal_amount,
            fee_amount=t.fee_amount,
            interest_amount=t.interest_amount,
            final_amount=t.final_amount,
            source_sheet=t.source_sheet,
            raw_data={k: str(v) for row in t.raw_rows for k, v in row.items()},
        ))

    session.commit()
    return import_file
