"""
Serviço de conciliação — carrega ERPTransaction/BankTransaction já
persistidos para uma competência, roda app.reconciliation.engine (a mesma
lógica validada no Golden Test) e grava o resultado como
ReconciliationMatchRow.

Não reimplementa nenhuma regra aqui — só adapta os modelos do banco para o
formato que o motor espera (dataclasses dos importadores) e volta.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.importers.banks.itau_francesinha import BankTransaction as BankTransactionDC
from app.importers.erp.crp032a1 import DocumentoRecebido as DocumentoRecebidoDC
from app.importers.erp.ffp045a2 import ERPTransaction as ERPTransactionDC
from app.models.bank_transaction import BankTransaction as BankTransactionRow
from app.models.documento_recebido import DocumentoRecebido as DocumentoRecebidoRow
from app.models.erp_transaction import ERPTransaction as ERPTransactionRow
from app.models.reconciliation import Reconciliation
from app.models.reconciliation_match import ReconciliationMatchRow
from app.reconciliation.engine import run_reconciliation


def _row_to_bank_dc(row: BankTransactionRow) -> BankTransactionDC:
    dc = BankTransactionDC(
        bank=row.bank, account=str(row.bank_account_id), movement_date=row.movement_date,
        nosso_numero=row.nosso_numero, seu_numero=row.seu_numero,
        normalized_title=row.normalized_title, payer_name=row.payer_name,
        operation_type=row.operation_type,
        principal_amount=float(row.principal_amount) if row.principal_amount is not None else None,
        fee_amount=float(row.fee_amount or 0), interest_amount=float(row.interest_amount or 0),
        final_amount=float(row.final_amount) if row.final_amount is not None else None,
        source_sheet=row.source_sheet or "",
        due_date=row.due_date,
        agency=row.agency,
    )
    dc._db_id = row.id  # referência de volta para persistir o match
    return dc


def _row_to_erp_dc(row: ERPTransactionRow) -> ERPTransactionDC:
    dc = ERPTransactionDC(
        account_local=row.account_local or "", transaction_date=row.transaction_date,
        invoice_number_raw=row.invoice_number_raw, normalized_title=row.normalized_title,
        tipo=row.tipo, tipo_documento=row.tipo_documento, nota_fiscal=row.nota_fiscal,
        descricao=row.descricao or "",
        incoming_amount=float(row.incoming_amount) if row.incoming_amount is not None else None,
        outgoing_amount=float(row.outgoing_amount) if row.outgoing_amount is not None else None,
        balance=float(row.balance) if row.balance is not None else None,
        is_anticipation=row.is_anticipation,
    )
    dc._db_id = row.id
    return dc


def _row_to_crp_dc(row: DocumentoRecebidoRow) -> DocumentoRecebidoDC:
    dc = DocumentoRecebidoDC(
        documento=row.documento, normalized_title=row.normalized_title, cliente=row.cliente,
        data_pagamento=row.data_pagamento,
        valor_emissao=float(row.valor_emissao) if row.valor_emissao is not None else None,
        impostos_retidos=float(row.impostos_retidos or 0), valor_desconto=float(row.valor_desconto or 0),
        valor_abatimento=float(row.valor_abatimento or 0), valor_juros=float(row.valor_juros or 0),
        valor_multa=float(row.valor_multa or 0),
        valor_pago=float(row.valor_pago) if row.valor_pago is not None else None,
    )
    dc._db_id = row.id
    return dc


def run_and_persist_reconciliation(session: Session, reconciliation_id: UUID) -> list[ReconciliationMatchRow]:
    reconciliation = session.get(Reconciliation, reconciliation_id)
    if reconciliation is None:
        raise ValueError(f"Reconciliation {reconciliation_id} não encontrada.")

    bank_rows = (
        session.query(BankTransactionRow)
        .filter_by(import_file_id=reconciliation.bank_import_file_id)
        .all()
    )
    erp_rows = (
        session.query(ERPTransactionRow)
        .filter_by(import_file_id=reconciliation.erp_import_file_id)
        .all()
    )

    bank_dcs = [_row_to_bank_dc(r) for r in bank_rows]
    erp_dcs = [_row_to_erp_dc(r) for r in erp_rows]

    crp_dcs = []
    if reconciliation.crp032a1_import_file_id:
        crp_rows = (
            session.query(DocumentoRecebidoRow)
            .filter_by(import_file_id=reconciliation.crp032a1_import_file_id)
            .all()
        )
        crp_dcs = [_row_to_crp_dc(r) for r in crp_rows]

    results = run_reconciliation(bank_dcs, erp_dcs, crp_dcs)

    # Substitui os resultados anteriores desta competência (reconciliar de
    # novo deve refletir o estado atual, não empilhar resultados velhos).
    session.query(ReconciliationMatchRow).filter_by(reconciliation_id=reconciliation.id).delete()

    saved: list[ReconciliationMatchRow] = []
    for r in results:
        row = ReconciliationMatchRow(
            reconciliation_id=reconciliation.id,
            bank_transaction_id=getattr(r.bank_tx, "_db_id", None) if r.bank_tx else None,
            erp_transaction_id=getattr(r.erp_tx, "_db_id", None) if r.erp_tx else None,
            documento_recebido_id=getattr(r.crp_doc, "_db_id", None) if r.crp_doc else None,
            status=r.status.value,
            confidence=r.confidence,
            diagnostic=r.diagnostic,
        )
        session.add(row)
        saved.append(row)

    return saved
