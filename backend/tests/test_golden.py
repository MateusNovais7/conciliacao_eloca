"""
Golden Test — MEATHUNTER / Itaú 98967-1 / janeiro-2026.

Os arquivos em tests/fixtures/ são os arquivos REAIS usados para construir
e validar o motor (ver item 29 do prompt original). As contagens abaixo
foram obtidas RODANDO o motor (ver saída do `python -m app.reconciliation.engine`
nesta mesma sessão) — não foram inventadas, e este teste existe justamente
para que uma mudança futura no motor não regrida esses números
silenciosamente.

Inclui o CRP032A1 (Relação de Documentos Recebidos) — fonte OPCIONAL que
explica desconto comercial em valores divergentes (Regra 12). Sem ele, os
6 casos ficariam como VALOR DIVERGENTE (ver test_regra12_desconto_...).

Se este teste falhar após uma mudança legítima no motor (ex: uma nova regra
implementada que reclassifica alguns dos 4 BANCO SEM ERP restantes), o
procedimento correto é: investigar CADA registro que mudou de status,
confirmar que a mudança é uma melhoria genuína (não uma heurística
inventada), e só então atualizar os números deste teste — nunca o
contrário (ajustar o teste sem entender a mudança).
"""
from collections import Counter
from pathlib import Path

import pytest

from app.importers.banks.itau_francesinha import import_itau_francesinha
from app.importers.erp.crp032a1 import import_crp032a1
from app.importers.erp.ffp045a2 import import_erp_ffp045a2
from app.reconciliation.engine import ReconciliationStatus, run_reconciliation

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def golden_results():
    bank_txs = import_itau_francesinha(FIXTURES / "itau_francesinha_janeiro2026.xlsx")
    erp_txs = import_erp_ffp045a2(FIXTURES / "erp_janeiro2026.xlsx")
    crp_docs = import_crp032a1(FIXTURES / "crp032a1_janeiro2026.xlsx")
    return run_reconciliation(bank_txs, erp_txs, crp_docs), bank_txs, erp_txs, crp_docs


def test_importacao_banco_encontra_todos_os_titulos(golden_results):
    _, bank_txs, _, _ = golden_results
    assert len(bank_txs) == 3047


def test_importacao_erp_encontra_todos_os_recebimentos(golden_results):
    _, _, erp_txs, _ = golden_results
    receivable = [t for t in erp_txs if t.is_receivable]
    assert len(receivable) == 1203


def test_importacao_crp032a1_encontra_todos_os_documentos(golden_results):
    _, _, _, crp_docs = golden_results
    assert len(crp_docs) == 3034
    com_desconto = [d for d in crp_docs if d.valor_desconto > 0]
    assert len(com_desconto) == 24


def test_taxa_de_conciliacao_nao_regride(golden_results):
    results, _, _, _ = golden_results
    counts = Counter(r.status for r in results)
    conciliados = sum(counts.get(s, 0) for s in (
        ReconciliationStatus.CONCILIADO,
        ReconciliationStatus.CONCILIADO_D1,
        ReconciliationStatus.CONCILIADO_D2,
        ReconciliationStatus.CORTE_COMPETENCIA,
        ReconciliationStatus.CORTE_FIM_PERIODO,
        ReconciliationStatus.CONCILIADO_DESCONTO,
    ))
    # Piso de segurança: obtido rodando o motor nesta sessão (8 + 639 + 128
    # + 228 + 51 + 6 = 1060, de um total de 1164 registros). Uma mudança
    # que derrube isso abaixo de 1055 precisa ser investigada antes de
    # mergear.
    assert conciliados >= 1055, (
        f"Conciliação caiu para {conciliados} registros — investigue antes de aceitar."
    )


def test_casos_reais_confirmados_continuam_corretos(golden_results):
    results, _, _, _ = golden_results

    # Caso normalização: Seu Número 700521 == Fatura/Seq 7005-21.
    matches = [r for r in results if r.bank_tx and r.bank_tx.seu_numero == "700521"]
    assert len(matches) == 1
    assert matches[0].status == ReconciliationStatus.CORTE_COMPETENCIA
    assert matches[0].erp_tx.invoice_number_raw == "7005-21"

    # Caso corte de competência de fim de período: 43 títulos batidos na
    # investigação manual desta sessão caem em 30/01 (última data do ERP).
    from datetime import date
    fim_periodo = [
        r for r in results
        if r.status == ReconciliationStatus.CORTE_FIM_PERIODO
        and r.bank_tx and r.bank_tx.movement_date == date(2026, 1, 30)
    ]
    assert len(fim_periodo) == 43

    # Caso título descontado: nenhuma 'liquidação de título descontado'
    # pode aparecer como BANCO SEM ERP nem VALOR DIVERGENTE (falso
    # positivo corrigido nesta sessão).
    descontados_mal_classificados = [
        r for r in results
        if r.bank_tx and r.bank_tx.operation_type == "liquidação de título descontado"
        and r.status != ReconciliationStatus.TITULO_DESCONTADO
    ]
    assert descontados_mal_classificados == []

    # Caso real de desconto comercial: título 34238-21 (Boteco Rios
    # Ipanema), R$ 3.725,84 no banco vs R$ 3.437,98 no ERP, explicado por
    # R$ 287,86 de desconto no CRP032A1.
    desconto_34238 = [
        r for r in results if r.bank_tx and r.bank_tx.seu_numero == "3423821"
    ]
    assert len(desconto_34238) == 1
    assert desconto_34238[0].status == ReconciliationStatus.CONCILIADO_DESCONTO


def test_regra12_desconto_resolve_todos_os_valor_divergente_de_janeiro(golden_results):
    """Achado real: os 6 casos de VALOR DIVERGENTE de janeiro/2026 batem
    100% com o desconto do CRP032A1 — nenhum sobra sem explicação."""
    results, _, _, _ = golden_results
    counts = Counter(r.status for r in results)
    assert counts.get(ReconciliationStatus.VALOR_DIVERGENTE, 0) == 0
    assert counts.get(ReconciliationStatus.CONCILIADO_DESCONTO, 0) == 6


def test_residuais_genuinos_estao_dentro_do_esperado(golden_results):
    """Após separar título descontado, fora-de-escopo (PIX/depósito),
    corte de fim de período e desconto comercial, sobra um resíduo pequeno
    e genuíno de casos que precisam de investigação manual."""
    results, _, _, _ = golden_results
    counts = Counter(r.status for r in results)
    assert counts.get(ReconciliationStatus.BANCO_SEM_ERP, 0) <= 10
    assert counts.get(ReconciliationStatus.ERP_SEM_BANCO, 0) <= 10
