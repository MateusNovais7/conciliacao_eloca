from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.auth import require_api_key
from app.database.deps import get_session
from app.models.audit_log import AuditAction, AuditLog
from app.models.bank_transaction import BankTransaction
from app.models.erp_transaction import ERPTransaction
from app.models.manual_adjustment import ManualAdjustment, ManualAdjustmentReason
from app.models.reconciliation import Reconciliation, ReconciliationLifecycleStatus
from app.models.reconciliation_match import ReconciliationMatchRow
from app.schemas.reconciliation import (
    DailyReconciliationRow,
    DashboardOut,
    DashboardStatusCount,
    ManualAdjustmentCreate,
    ReconciliationCreate,
    ReconciliationHistoryItem,
    ReconciliationMatchDetailOut,
    ReconciliationMatchOut,
    ReconciliationOut,
)
from app.services.reconciliation_service import run_and_persist_reconciliation

router = APIRouter(prefix="/conciliacoes", tags=["conciliacoes"])

RECONCILED_STATUSES = {
    "CONCILIADO", "CONCILIADO D+1", "CONCILIADO D+2",
    "CORTE DE COMPETÊNCIA", "CORTE DE COMPETÊNCIA (fim do período importado)",
    "CONCILIADO MANUALMENTE",
}


OUT_OF_SCOPE_STATUSES = {"TÍTULO DESCONTADO (fora do escopo desta versão)"}


def _get_reconciliation_or_404(session: Session, reconciliation_id: UUID) -> Reconciliation:
    reconciliation = session.get(Reconciliation, reconciliation_id)
    if reconciliation is None:
        raise HTTPException(status_code=404, detail="Conciliação não encontrada.")
    return reconciliation


def _compute_reconciled_pct(session: Session, reconciliation_id: UUID) -> float:
    counts = Counter(
        status for (status,) in
        session.query(ReconciliationMatchRow.status).filter_by(reconciliation_id=reconciliation_id).all()
    )
    total_in_scope = sum(c for s, c in counts.items() if s not in OUT_OF_SCOPE_STATUSES)
    if not total_in_scope:
        return 0.0
    reconciled = sum(c for s, c in counts.items() if s in RECONCILED_STATUSES)
    return round(100 * reconciled / total_in_scope, 2)


@router.delete("/{reconciliation_id}", status_code=204)
def delete_reconciliation(
    reconciliation_id: UUID, performed_by: str,
    session: Session = Depends(get_session), _=Depends(require_api_key),
):
    """Item 39/19 — exclusão é permitida, mas nunca silenciosa: gera log de
    auditoria com o estado anterior, e é bloqueada para competências
    FECHADA (reabra antes se realmente precisar apagar)."""
    reconciliation = _get_reconciliation_or_404(session, reconciliation_id)
    if reconciliation.status == ReconciliationLifecycleStatus.FECHADA:
        raise HTTPException(
            status_code=409,
            detail="Esta competência está fechada. Reabra antes de excluir.",
        )

    match_ids = [
        row.id for row in
        session.query(ReconciliationMatchRow.id).filter_by(reconciliation_id=reconciliation.id).all()
    ]
    if match_ids:
        session.query(ManualAdjustment).filter(
            ManualAdjustment.reconciliation_match_id.in_(match_ids)
        ).delete(synchronize_session=False)
        session.query(ReconciliationMatchRow).filter(
            ReconciliationMatchRow.id.in_(match_ids)
        ).delete(synchronize_session=False)

    session.add(AuditLog(
        action=AuditAction.EXCLUSAO, entity_type="Reconciliation", entity_id=reconciliation.id,
        performed_by=performed_by,
        before={
            "competencia_year": reconciliation.competencia_year,
            "competencia_month": reconciliation.competencia_month,
            "status": reconciliation.status.value,
        },
    ))
    session.delete(reconciliation)
    session.commit()


@router.get("", response_model=list[ReconciliationHistoryItem])
def list_reconciliations(
    bank_account_id: UUID,
    session: Session = Depends(get_session),
    _=Depends(require_api_key),
):
    """Item 22 — histórico de competências de uma conta, com o percentual
    já calculado, para a tela de histórico do cliente não obrigar o
    usuário a reimportar tudo de novo só pra ver onde parou."""
    reconciliations = (
        session.query(Reconciliation)
        .filter_by(bank_account_id=bank_account_id)
        .order_by(Reconciliation.competencia_year.desc(), Reconciliation.competencia_month.desc())
        .all()
    )
    return [
        ReconciliationHistoryItem(
            id=r.id, competencia_year=r.competencia_year, competencia_month=r.competencia_month,
            status=r.status.value, reconciled_pct=_compute_reconciled_pct(session, r.id),
            created_at=r.created_at, closed_at=r.closed_at,
        )
        for r in reconciliations
    ]


@router.post("", response_model=ReconciliationOut, status_code=201)
def create_reconciliation(payload: ReconciliationCreate, session: Session = Depends(get_session), _=Depends(require_api_key)):
    reconciliation = Reconciliation(**payload.model_dump())
    session.add(reconciliation)
    session.flush()
    session.commit()
    return reconciliation


@router.post("/{reconciliation_id}/executar", response_model=list[ReconciliationMatchOut])
def executar_conciliacao(reconciliation_id: UUID, session: Session = Depends(get_session), _=Depends(require_api_key)):
    reconciliation = _get_reconciliation_or_404(session, reconciliation_id)
    if reconciliation.status == ReconciliationLifecycleStatus.FECHADA:
        raise HTTPException(
            status_code=409,
            detail="Esta competência está fechada. Reabra antes de rodar o motor novamente.",
        )

    matches = run_and_persist_reconciliation(session, reconciliation_id)
    if reconciliation.status == ReconciliationLifecycleStatus.RASCUNHO:
        reconciliation.status = ReconciliationLifecycleStatus.EM_ANALISE
    session.flush()

    session.add(AuditLog(
        action=AuditAction.CONCILIACAO, entity_type="Reconciliation", entity_id=reconciliation.id,
        performed_by="sistema", context={"matches_gerados": len(matches)},
    ))
    session.commit()
    return matches


@router.get("/{reconciliation_id}/dashboard", response_model=DashboardOut)
def dashboard(reconciliation_id: UUID, session: Session = Depends(get_session), _=Depends(require_api_key)):
    reconciliation = _get_reconciliation_or_404(session, reconciliation_id)
    matches = session.query(ReconciliationMatchRow).filter_by(reconciliation_id=reconciliation.id).all()

    counts = Counter(m.status for m in matches)
    by_status = []
    for status, count in counts.items():
        amount = 0.0
        for m in matches:
            if m.status != status:
                continue
            if m.bank_transaction and m.bank_transaction.principal_amount is not None:
                amount += float(m.bank_transaction.client_amount or 0)
            elif m.erp_transaction and m.erp_transaction.incoming_amount is not None:
                amount += float(m.erp_transaction.incoming_amount)
        by_status.append(DashboardStatusCount(status=status, count=count, total_amount=round(amount, 2)))

    reconciled_count = sum(c.count for c in by_status if c.status in RECONCILED_STATUSES)
    reconciled_amount = sum(c.total_amount for c in by_status if c.status in RECONCILED_STATUSES)
    divergent_amount = sum(c.total_amount for c in by_status if c.status == "VALOR DIVERGENTE")

    # % de conciliação é calculada sobre o universo de títulos realmente no
    # escopo do matching — exclui 'título descontado' (carteira de
    # antecipação bancária, fora do escopo desta versão, ver engine.py),
    # senão o denominador fica inflado com registros que nunca poderiam
    # ser conciliados por título+valor.
    in_scope_count = sum(c.count for c in by_status if c.status not in OUT_OF_SCOPE_STATUSES)


    bank_titles_count = session.query(BankTransaction).filter_by(
        bank_account_id=reconciliation.bank_account_id,
        import_file_id=reconciliation.bank_import_file_id,
    ).count()
    erp_titles_count = session.query(ERPTransaction).filter_by(
        bank_account_id=reconciliation.bank_account_id,
        import_file_id=reconciliation.erp_import_file_id,
    ).count()

    return DashboardOut(
        reconciliation_id=reconciliation.id,
        bank_titles_count=bank_titles_count,
        erp_titles_count=erp_titles_count,
        reconciled_count=reconciled_count,
        reconciled_pct=round(100 * reconciled_count / in_scope_count, 2) if in_scope_count else 0.0,
        reconciled_amount=round(reconciled_amount, 2),
        divergent_amount=round(divergent_amount, 2),
        by_status=by_status,
    )


@router.get("/{reconciliation_id}/titulos", response_model=list[ReconciliationMatchOut])
def listar_titulos(
    reconciliation_id: UUID,
    status: str | None = None,
    search: str | None = Query(default=None, description="Busca por título, cliente, valor, NF ou documento"),
    session: Session = Depends(get_session),
    _=Depends(require_api_key),
):
    query = session.query(ReconciliationMatchRow).filter_by(reconciliation_id=reconciliation_id)
    if status:
        query = query.filter_by(status=status)

    rows = query.all()

    if search:
        needle = search.strip().lower()

        def matches_search(m: ReconciliationMatchRow) -> bool:
            haystacks = []
            if m.bank_transaction:
                haystacks += [m.bank_transaction.seu_numero, m.bank_transaction.payer_name,
                              str(m.bank_transaction.principal_amount)]
            if m.erp_transaction:
                haystacks += [m.erp_transaction.invoice_number_raw, m.erp_transaction.nota_fiscal,
                              str(m.erp_transaction.incoming_amount)]
            return any(needle in str(h).lower() for h in haystacks if h)

        rows = [m for m in rows if matches_search(m)]

    return rows


@router.get("/{reconciliation_id}/titulos/{match_id}", response_model=ReconciliationMatchDetailOut)
def detalhe_titulo(
    reconciliation_id: UUID, match_id: UUID,
    session: Session = Depends(get_session), _=Depends(require_api_key),
):
    match = session.get(ReconciliationMatchRow, match_id)
    if match is None or match.reconciliation_id != reconciliation_id:
        raise HTTPException(status_code=404, detail="Registro de conciliação não encontrado.")
    return match


@router.post("/{reconciliation_id}/titulos/{match_id}/ajuste-manual", response_model=ReconciliationMatchOut)
def ajuste_manual(
    reconciliation_id: UUID, match_id: UUID, payload: ManualAdjustmentCreate,
    session: Session = Depends(get_session), _=Depends(require_api_key),
):
    reconciliation = _get_reconciliation_or_404(session, reconciliation_id)
    if reconciliation.status == ReconciliationLifecycleStatus.FECHADA:
        raise HTTPException(status_code=409, detail="Competência fechada — não é possível ajustar. Reabra antes.")

    match = session.get(ReconciliationMatchRow, match_id)
    if match is None or match.reconciliation_id != reconciliation_id:
        raise HTTPException(status_code=404, detail="Registro de conciliação não encontrado.")

    try:
        reason = ManualAdjustmentReason(payload.reason)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Motivo inválido. Use um de: {', '.join(r.value for r in ManualAdjustmentReason)}",
        )

    previous_status = match.status
    session.add(ManualAdjustment(
        reconciliation_match_id=match.id, reason=reason, observation=payload.observation,
        previous_status=previous_status, new_status=payload.new_status,
        performed_by=payload.performed_by,
    ))
    match.status = payload.new_status
    match.is_manual_override = True
    session.flush()

    session.add(AuditLog(
        action=AuditAction.AJUSTE_MANUAL, entity_type="ReconciliationMatchRow", entity_id=match.id,
        performed_by=payload.performed_by,
        before={"status": previous_status}, after={"status": payload.new_status},
        context={"reason": reason.value, "observation": payload.observation},
    ))
    session.commit()
    return match


@router.get("/{reconciliation_id}/diaria", response_model=list[DailyReconciliationRow])
def conciliacao_diaria(reconciliation_id: UUID, session: Session = Depends(get_session), _=Depends(require_api_key)):
    """Item 16 — compara o total liquidado no banco com o total baixado no
    ERP, dia a dia, para responder 'em qual dia ERP e banco deixaram de
    fechar'. Os totais são independentes do pareamento título a título
    (um título D+1 conta no dia em que o dinheiro efetivamente moveu em
    cada lado) — é isso que deixa visível um dia com diferença mesmo
    quando, título a título, tudo está com status CONCILIADO D+1."""
    from app.reconciliation.engine import SETTLEMENT_OPERATION_TYPES, ERP_TIPO_DOCUMENTO_IN_SCOPE

    reconciliation = _get_reconciliation_or_404(session, reconciliation_id)

    bank_rows = session.query(BankTransaction).filter_by(
        import_file_id=reconciliation.bank_import_file_id,
        bank_account_id=reconciliation.bank_account_id,
    ).all()
    erp_rows = session.query(ERPTransaction).filter_by(
        import_file_id=reconciliation.erp_import_file_id,
        bank_account_id=reconciliation.bank_account_id,
    ).all()

    bank_by_day: dict = {}
    for b in bank_rows:
        if b.operation_type not in SETTLEMENT_OPERATION_TYPES:
            continue
        bank_by_day.setdefault(b.movement_date, 0.0)
        bank_by_day[b.movement_date] += float(b.client_amount or 0)

    erp_by_day: dict = {}
    for e in erp_rows:
        if e.tipo != "Rec. Dup." or e.is_anticipation or e.tipo_documento not in ERP_TIPO_DOCUMENTO_IN_SCOPE:
            continue
        erp_by_day.setdefault(e.transaction_date, 0.0)
        erp_by_day[e.transaction_date] += float(e.incoming_amount or 0)

    matches = session.query(ReconciliationMatchRow).filter_by(reconciliation_id=reconciliation_id).all()
    match_ids_by_day: dict = {}
    for m in matches:
        day = m.bank_transaction.movement_date if m.bank_transaction else (
            m.erp_transaction.transaction_date if m.erp_transaction else None
        )
        if day is None:
            continue
        match_ids_by_day.setdefault(day, []).append(m.id)

    all_days = sorted(set(bank_by_day) | set(erp_by_day))
    rows = []
    for day in all_days:
        bank_total = round(bank_by_day.get(day, 0.0), 2)
        erp_total = round(erp_by_day.get(day, 0.0), 2)
        diff = round(bank_total - erp_total, 2)
        rows.append(DailyReconciliationRow(
            date=day, bank_total=bank_total, erp_total=erp_total, difference=diff,
            status="OK" if abs(diff) < 0.01 else "DIVERGENTE",
            match_ids=match_ids_by_day.get(day, []),
        ))
    return rows


@router.post("/{reconciliation_id}/fechar", response_model=ReconciliationOut)
def fechar_competencia(
    reconciliation_id: UUID, performed_by: str,
    session: Session = Depends(get_session), _=Depends(require_api_key),
):
    reconciliation = _get_reconciliation_or_404(session, reconciliation_id)
    reconciliation.status = ReconciliationLifecycleStatus.FECHADA
    reconciliation.closed_at = datetime.now(timezone.utc)
    reconciliation.closed_by = performed_by
    session.flush()

    session.add(AuditLog(
        action=AuditAction.FECHAMENTO, entity_type="Reconciliation", entity_id=reconciliation.id,
        performed_by=performed_by,
    ))
    session.commit()
    return reconciliation


@router.post("/{reconciliation_id}/reabrir", response_model=ReconciliationOut)
def reabrir_competencia(
    reconciliation_id: UUID, performed_by: str,
    session: Session = Depends(get_session), _=Depends(require_api_key),
):
    reconciliation = _get_reconciliation_or_404(session, reconciliation_id)
    reconciliation.status = ReconciliationLifecycleStatus.REABERTA
    session.flush()

    session.add(AuditLog(
        action=AuditAction.REABERTURA, entity_type="Reconciliation", entity_id=reconciliation.id,
        performed_by=performed_by,
    ))
    session.commit()
    return reconciliation
