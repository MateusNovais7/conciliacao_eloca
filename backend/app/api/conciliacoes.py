from __future__ import annotations

import io
from collections import Counter
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, StreamingResponse
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
    RecoveredTitleOut,
)
from app.services.reconciliation_service import run_and_persist_reconciliation
from app.services.recovery_service import RecoveredTitle, find_recoverable_titles

router = APIRouter(prefix="/conciliacoes", tags=["conciliacoes"])

RECONCILED_STATUSES = {
    "CONCILIADO", "CONCILIADO D+1", "CONCILIADO D+2",
    "CORTE DE COMPETÊNCIA", "CORTE DE COMPETÊNCIA (fim do período importado)",
    "CONCILIADO MANUALMENTE", "CONCILIADO (desconto)", "CONCILIADO (título descontado)",
}


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
    total = sum(counts.values())
    if not total:
        return 0.0
    reconciled = sum(c for s, c in counts.items() if s in RECONCILED_STATUSES)
    return round(100 * reconciled / total, 2)


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


@router.get("/{reconciliation_id}", response_model=ReconciliationOut)
def get_reconciliation(reconciliation_id: UUID, session: Session = Depends(get_session), _=Depends(require_api_key)):
    return _get_reconciliation_or_404(session, reconciliation_id)


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

    # % de conciliação sobre o total de registros do motor. Título
    # descontado deixou de ser tratado como estruturalmente fora de escopo
    # (Regra 13 já explica a maioria via antecipação/CRP032A1) — o que
    # sobrar sem explicação entra no denominador como qualquer outro
    # residual (banco-sem-ERP, ERP-sem-banco), sem inflar nem esconder.
    total_matches = sum(c.count for c in by_status)

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
        reconciled_pct=round(100 * reconciled_count / total_matches, 2) if total_matches else 0.0,
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


@router.get("/{reconciliation_id}/recuperacao", response_model=list[RecoveredTitleOut])
def listar_titulos_recuperaveis(
    reconciliation_id: UUID, session: Session = Depends(get_session), _=Depends(require_api_key),
):
    """Cruza os 'TÍTULO DESCONTADO SEM CORRESPONDÊNCIA' com o FTP050
    (Relação de NF Emitidas) para descobrir Local e Cliente de documentos
    apagados por engano — ver app/services/recovery_service.py."""
    _get_reconciliation_or_404(session, reconciliation_id)
    try:
        return find_recoverable_titles(session, reconciliation_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


def _recovered_to_row(r: RecoveredTitle) -> dict:
    return {
        "Local": r.local_id if r.resolved else None,
        "Duplicata": r.nota_fiscal,
        "Sequência": r.sequencia,
        "Status": "Cobrança Ativa",
        "Cliente": r.cliente_id if r.resolved else None,
        "Data Emissão": None,  # preenchido no export a partir do FTP050 (ver nota)
        "Vencimento": r.due_date.strftime("%d/%m/%Y") if r.due_date else None,
        "Valor de Emissão": r.principal_amount,
        "Banco": 341,
        "Agência": r.agency,
        "Tipo Documento": "BOLETO BANCARIO [5]",
        "Forma Pagamento NF-e 4.0": "Boleto Bancário-[15]",
        "Número do Título": r.nosso_numero,
        "_Seu Número (banco)": r.seu_numero,
        "_Pagador (banco)": r.payer_name,
        "_Razão Social (FTP050)": r.razao_social,
        "_Local (nome)": r.local_nome,
        "_Data liquidação banco": r.movement_date.strftime("%d/%m/%Y"),
        "_Resolvido": "SIM" if r.resolved else "NÃO — revisar manualmente",
    }


@router.get("/{reconciliation_id}/recuperacao/excel")
def exportar_recuperacao_excel(
    reconciliation_id: UUID, session: Session = Depends(get_session), _=Depends(require_api_key),
):
    import pandas as pd
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.comments import Comment
    from openpyxl.utils import get_column_letter

    reconciliation = _get_reconciliation_or_404(session, reconciliation_id)
    titulos = find_recoverable_titles(session, reconciliation_id)

    FORM_COLS = [
        "Local", "Duplicata", "Sequência", "Status", "Cliente", "Data Emissão",
        "Vencimento", "Valor de Emissão", "Banco", "Agência", "Tipo Documento",
        "Forma Pagamento NF-e 4.0", "Número do Título",
    ]
    REF_COLS = [
        "_Seu Número (banco)", "_Pagador (banco)", "_Razão Social (FTP050)",
        "_Local (nome)", "_Data liquidação banco", "_Resolvido",
    ]
    ALL_COLS = FORM_COLS + REF_COLS

    wb = Workbook()
    ws = wb.active
    ws.title = "Documentos a reimputar"

    header_font = Font(name="Arial", bold=True, color="FFFFFF", size=10)
    header_fill = PatternFill("solid", fgColor="0F766E")
    ref_header_fill = PatternFill("solid", fgColor="78716C")
    cell_font = Font(name="Arial", size=10)
    ref_cell_font = Font(name="Arial", size=10, italic=True, color="57534E")
    thin = Side(style="thin", color="D6D3D1")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col_idx, col_name in enumerate(ALL_COLS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name.lstrip("_"))
        cell.font = header_font
        cell.fill = header_fill if col_name in FORM_COLS else ref_header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border

    valor_col_idx = FORM_COLS.index("Valor de Emissão") + 1
    ws.cell(row=1, column=valor_col_idx).comment = Comment(
        "Extraído da coluna 'Valor Inicial (R$)' da Francesinha — a 'Valor Final (R$)' "
        "vem R$ 0,00 para título descontado (carteira de antecipação bancária). "
        "Confirmar antes de importar em massa.",
        "Sistema de Conciliação",
    )

    for row_idx, t in enumerate(titulos, start=2):
        row = _recovered_to_row(t)
        for col_idx, col_name in enumerate(ALL_COLS, start=1):
            value = row.get(col_name)
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = cell_font if col_name in FORM_COLS else ref_cell_font
            cell.border = border
            if col_name == "Valor de Emissão" and value is not None:
                cell.number_format = "#,##0.00"
            if col_name == "_Resolvido" and value != "SIM":
                cell.font = Font(name="Arial", size=10, bold=True, color="B91C1C")

    widths = {
        "Local": 8, "Duplicata": 11, "Sequência": 10, "Status": 15, "Cliente": 9,
        "Data Emissão": 13, "Vencimento": 12, "Valor de Emissão": 15, "Banco": 8,
        "Agência": 9, "Tipo Documento": 20, "Forma Pagamento NF-e 4.0": 22,
        "Número do Título": 15, "_Seu Número (banco)": 16, "_Pagador (banco)": 30,
        "_Razão Social (FTP050)": 45, "_Local (nome)": 16, "_Data liquidação banco": 16,
        "_Resolvido": 22,
    }
    for col_idx, col_name in enumerate(ALL_COLS, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = widths.get(col_name, 14)
    ws.freeze_panes = "A2"
    if titulos:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(ALL_COLS))}{len(titulos) + 1}"

    legend = wb.create_sheet("Legenda")
    legend.cell(row=1, column=1, value="Legenda").font = Font(name="Arial", bold=True, size=12)
    notas = [
        "",
        "Colunas VERDES: campos exatos do formulário do ERP (CRP015A1).",
        "Colunas CINZAS: dados de referência/auditoria — não fazem parte do formulário.",
        "'Local'/'Cliente' vazios e '_Resolvido' = NÃO: a NF não foi encontrada com confiança no FTP050 — revisar manualmente antes de importar.",
        "Valor de Emissão vem de 'Valor Inicial (R$)' da Francesinha (ver comentário na célula do cabeçalho).",
        "Data Emissão não veio automaticamente neste export — consultar o FTP050 pelo número da NF (coluna Duplicata) e preencher manualmente.",
    ]
    for i, nota in enumerate(notas, start=2):
        legend.cell(row=i, column=1, value=nota).font = Font(name="Arial", size=10)
    legend.column_dimensions["A"].width = 100

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    filename = f"reimputacao_{reconciliation.competencia_year}_{reconciliation.competencia_month:02d}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{reconciliation_id}/recuperacao/script", response_class=PlainTextResponse)
def exportar_recuperacao_script(
    reconciliation_id: UUID, session: Session = Depends(get_session), _=Depends(require_api_key),
):
    """Gera um script para colar no console (F12) da tela de cadastro do
    título (CRP015A1). IMPORTANTE — limite real e assumido: só os campos
    de texto simples (Duplicata, Sequência, Cliente, Datas, Valor, Título)
    são preenchidos automaticamente via o atributo 'name' de cada input,
    que é confiável. Os 4 campos de busca (Local, Status, Tipo Documento,
    Forma Pagamento) são um widget customizado sem um seletor confiável
    visível a partir do HTML fornecido — o script digita o valor na caixa
    de busca para disparar a busca automática do próprio ERP, mas não
    tenta selecionar a sugestão sozinho. Precisa confirmar manualmente."""
    _get_reconciliation_or_404(session, reconciliation_id)
    titulos = find_recoverable_titles(session, reconciliation_id)
    reconciliation = session.get(Reconciliation, reconciliation_id)
    account_number = reconciliation.bank_account.account_number if reconciliation.bank_account else ""

    import json
    payload = [
        {
            "nf": t.nota_fiscal, "seq": t.sequencia,
            "cliente": t.cliente_id, "clienteNome": t.razao_social,
            "vencimento": t.due_date.strftime("%d/%m/%Y") if t.due_date else "",
            "valor": t.principal_amount, "agencia": t.agency,
            "numeroTitulo": t.nosso_numero,
            "localId": t.local_id, "localNome": t.local_nome,
            "resolvido": t.resolved,
            "seuNumero": t.seu_numero,
        }
        for t in titulos
    ]

    script = f"""// Script gerado pelo Sistema de Conciliação — reimputação de documentos apagados.
// Cole no console (F12) da tela do CRP015A1, com o formulário de NOVO documento aberto.
//
// LIMITE CONHECIDO: preenche com segurança os campos de texto simples (Duplicata,
// Sequência, Cliente, Vencimento, Valor de Emissão, Agência, Número do Título).
// Local, Status, Tipo Documento e Forma Pagamento são campos de busca customizados —
// o script digita o valor pra disparar a busca automática do ERP, mas você precisa
// confirmar/selecionar a sugestão certa manualmente (não seleciona sozinho).
//
// Uso: rode window.reimputacao.preencher() para o documento atual, depois de
// SALVAR no ERP rode window.reimputacao.proximo() e preencher() de novo.

window.reimputacao = (function () {{
  const documentos = {json.dumps(payload, ensure_ascii=False, indent=2)};
  let indice = 0;

  function disparar(el, tipo) {{
    el.dispatchEvent(new Event(tipo, {{ bubbles: true }}));
  }}

  function setCampo(name, valor) {{
    const el = document.querySelector(`[name="${{name}}"]`);
    if (!el) {{ console.warn(`Campo ${{name}} não encontrado na tela atual.`); return; }}
    el.value = valor ?? "";
    disparar(el, "input");
    disparar(el, "keyup");
    disparar(el, "change");
  }}

  function preencher() {{
    const doc = documentos[indice];
    if (!doc) {{ console.log("Não há mais documentos."); return; }}
    console.log(`Preenchendo ${{indice + 1}}/${{documentos.length}} — NF ${{doc.nf}}-${{doc.seq}} (${{doc.clienteNome ?? "cliente não resolvido"}})`);
    if (!doc.resolvido) {{
      console.warn("Este documento NÃO foi resolvido com confiança (Local/Cliente ausentes) — preencha manualmente.");
    }}
    setCampo("NUMFATURA", doc.nf);
    setCampo("NUMSEQUENCIA", doc.seq);
    setCampo("CODCLIENTE", doc.cliente);
    setCampo("DATAVENCTO", doc.vencimento);
    setCampo("VALOREMISSAO", doc.valor != null ? String(doc.valor).replace(".", ",") : "");
    setCampo("CONTACORRENTE", "{account_number}");
    setCampo("NUMTITULO", doc.numeroTitulo);

    console.log(`Local esperado: ${{doc.localNome ?? "?"}} [${{doc.localId ?? "?"}}] — selecione manualmente no campo Local.`);
    console.log("Confirme também Status = Cobrança Ativa, Tipo Documento = BOLETO BANCARIO [5], Forma Pagamento = Boleto Bancário-[15].");
  }}

  function proximo() {{
    indice += 1;
    if (indice >= documentos.length) {{ console.log("Fim da lista."); return; }}
    preencher();
  }}

  function atual() {{ return documentos[indice]; }}

  return {{ documentos, preencher, proximo, atual, total: documentos.length }};
}})();

console.log(`Carregados ${{window.reimputacao.total}} documentos. Rode window.reimputacao.preencher() para começar.`);
"""
    return PlainTextResponse(content=script, media_type="application/javascript")


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
