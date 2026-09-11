from __future__ import annotations

import io
from collections import defaultdict
from uuid import UUID

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.auth import require_api_key
from app.database.deps import get_session
from app.models.manual_adjustment import ManualAdjustment
from app.models.reconciliation import Reconciliation
from app.models.reconciliation_match import ReconciliationMatchRow

router = APIRouter(prefix="/exports", tags=["exports"])

# Item 23 — nomes de aba e o status do motor que cada uma reúne.
SHEET_STATUS_MAP = {
    "CONCILIADOS": {"CONCILIADO", "CONCILIADO D+1", "CONCILIADO D+2", "CONCILIADO MANUALMENTE"},
    "BANCO_SEM_ERP": {"BANCO SEM ERP"},
    "ERP_SEM_BANCO": {"ERP SEM BANCO"},
    "VALOR_DIVERGENTE": {"VALOR DIVERGENTE"},
    "CORTE_PERIODO": {"CORTE DE COMPETÊNCIA", "CORTE DE COMPETÊNCIA (fim do período importado)"},
}


def _match_to_row(m: ReconciliationMatchRow) -> dict:
    b, e = m.bank_transaction, m.erp_transaction
    return {
        "Status": m.status,
        "Confiança (%)": m.confidence,
        "Título Banco": b.seu_numero if b else None,
        "Pagador": b.payer_name if b else None,
        "Data Banco": b.movement_date if b else None,
        "Valor Banco (Cliente)": float(b.client_amount) if b and b.client_amount is not None else None,
        "Título ERP": e.invoice_number_raw if e else None,
        "Data ERP": e.transaction_date if e else None,
        "Valor ERP": float(e.incoming_amount) if e and e.incoming_amount is not None else None,
        "Diagnóstico": m.diagnostic,
    }


@router.get("/{reconciliation_id}/excel")
def export_excel(reconciliation_id: UUID, session: Session = Depends(get_session), _=Depends(require_api_key)):
    reconciliation = session.get(Reconciliation, reconciliation_id)
    if reconciliation is None:
        raise HTTPException(status_code=404, detail="Conciliação não encontrada.")

    matches = session.query(ReconciliationMatchRow).filter_by(reconciliation_id=reconciliation_id).all()
    rows = [_match_to_row(m) for m in matches]
    df_all = pd.DataFrame(rows)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        # RESUMO
        resumo = pd.DataFrame([
            {"Status": status, "Quantidade": len(sub), "Valor Total": sub["Valor Banco (Cliente)"].fillna(
                sub["Valor ERP"]).sum() if not sub.empty else 0}
            for status, sub in df_all.groupby("Status")
        ]) if not df_all.empty else pd.DataFrame(columns=["Status", "Quantidade", "Valor Total"])
        resumo.to_excel(writer, sheet_name="RESUMO", index=False)

        for sheet_name, statuses in SHEET_STATUS_MAP.items():
            sub = df_all[df_all["Status"].isin(statuses)] if not df_all.empty else df_all
            (sub if not sub.empty else pd.DataFrame(columns=df_all.columns)).to_excel(
                writer, sheet_name=sheet_name, index=False,
            )

        # CONCILIACAO_DIARIA — agrupa por data do banco.
        if not df_all.empty and df_all["Data Banco"].notna().any():
            diaria = df_all.dropna(subset=["Data Banco"]).groupby("Data Banco").agg(
                Quantidade=("Status", "count"),
                Valor_Banco=("Valor Banco (Cliente)", "sum"),
            ).reset_index()
        else:
            diaria = pd.DataFrame(columns=["Data Banco", "Quantidade", "Valor_Banco"])
        diaria.to_excel(writer, sheet_name="CONCILIACAO_DIARIA", index=False)

        # AJUSTES_MANUAIS
        adjustments = (
            session.query(ManualAdjustment)
            .join(ReconciliationMatchRow)
            .filter(ReconciliationMatchRow.reconciliation_id == reconciliation_id)
            .all()
        )
        df_adj = pd.DataFrame([{
            "Motivo": a.reason.value, "De": a.previous_status, "Para": a.new_status,
            "Observação": a.observation, "Realizado por": a.performed_by, "Data/Hora": a.performed_at,
        } for a in adjustments]) if adjustments else pd.DataFrame(
            columns=["Motivo", "De", "Para", "Observação", "Realizado por", "Data/Hora"]
        )
        df_adj.to_excel(writer, sheet_name="AJUSTES_MANUAIS", index=False)

    buffer.seek(0)
    filename = f"conciliacao_{reconciliation.competencia_year}_{reconciliation.competencia_month:02d}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
