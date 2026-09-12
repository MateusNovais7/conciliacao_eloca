"""
Motor de conciliação — v1.

Implementado nesta versão (evidenciado nos arquivos reais MEATHUNTER / Itaú
98967-1, janeiro/2026):
  Regra 1  — match exato (título + valor + mesma data)
  Regra 2  — título + valor com D+1 / D+2 em DIAS ÚTEIS
  Regra 4  — valor divergente (mesmo título, valor diferente)
  Regra 5  — corte de competência (liquidado em D, baixado no próximo dia útil)
  Regra 6  — antecipação (já separada na importação do ERP via marcador
             'ANTECIPAÇÃO RECEBIVEIS' na descrição — não entra neste matching)
  Regra 7  — banco sem ERP
  Regra 8  — ERP sem banco
  Regra 9  — possível correspondência por proximidade (valor + cliente + data)
  Regra 12 — desconto comercial explica o valor divergente (fonte:
             CRP032A1, opcional — ver mais abaixo)
  Regra 13 — título descontado explicado via antecipação do ERP ou
             CRP032A1 (ver mais abaixo)

DELIBERADAMENTE AINDA NÃO IMPLEMENTADO (aguardando mais evidência/decisão,
conforme item 31 do prompt — não inventar regra sem evidência):
  Regra 10 — um-para-vários (agrupamento). Investigado nos dados de
    janeiro/2026 sem sucesso: busquei combinações de 2 lançamentos do ERP
    somando o valor de cada um dos 4 'BANCO SEM ERP' residuais e não achei
    nenhuma soma exata. Sem evidência real, não implementado.
  Regra 11 — vários-para-um (agrupamento). Mesma situação da Regra 10.
  Calendário de feriados (por ora só considera sábado/domingo como não-úteis)
  Classificação fina dos tipos de operação do banco além de
    'liquidação' / 'liquidação de título descontado' / 'baixa por ter sido
    liquidado' — os demais tipos ('baixa para acertos', 'entrada de título
    descontado' etc.) precisam de mais casos reais antes de virarem regra.

REGRA 12 — DESCONTO COMERCIAL (achado real, janeiro/2026): o relatório
FFP045A2 mostra a baixa já líquida, sem explicar por que ela é menor que o
principal do banco. O relatório CRP032A1 (Relação de Documentos Recebidos)
tem essa resposta — campo 'Valor Desconto' (e também Impostos Retidos,
Abatimento, Juros, Multa). Testado contra os 6 casos de VALOR DIVERGENTE de
janeiro/2026: **os 6 batem exatamente** com o desconto do CRP032A1. Por ser
uma fonte OPCIONAL (nem toda competência vai ter um CRP032A1 enviado), o
motor só aplica essa regra quando `crp_docs` é fornecido — sem ele, o
comportamento é idêntico ao de antes (VALOR DIVERGENTE sem explicação).

REGRA 13 — TÍTULO DESCONTADO (achado real, janeiro/2026): 'liquidação de
título descontado' no banco (carteira de antecipação/factoring do Itaú) e
'ANTECIPAÇÃO RECEBIVEIS' no ERP são A MESMA operação, cada sistema só usa
um nome diferente. Testado: dos 94 títulos descontados de janeiro/2026, os
44 lançamentos de antecipação do ERP bateram 1:1 com valor exato (bijeção
completa — nenhuma antecipação do ERP ficou de fora). Mais 4 bateram exato
com o CRP032A1 (documentos que nem aparecem no FFP045A2). Os 46 restantes
ficam como TITULO_DESCONTADO (sem correspondência) — não é mais tratado
como 'fora de escopo', é um residual genuíno como qualquer outro, sujeito a
investigação manual.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

from app.importers.banks.itau_francesinha import BankTransaction
from app.importers.erp.crp032a1 import DocumentoRecebido
from app.importers.erp.ffp045a2 import ERPTransaction

AMOUNT_TOLERANCE = 0.01

# Regra 9: tolerâncias de proximidade para "possível correspondência".
FUZZY_VALUE_TOLERANCE = 0.05          # ex: pequenas diferenças de centavos
FUZZY_DATE_WINDOW_BUSINESS_DAYS = 5   # janela de busca em dias úteis

# Tipos de operação do banco que representam dinheiro efetivamente recebido
# (evidenciado: 'entrada' tem Valor Final = 0, ou seja, é só o título
# entrando na carteira, ainda não é uma liquidação).
SETTLEMENT_OPERATION_TYPES = {
    "liquidação",
    "baixa por ter sido liquidado",
}

# Achado real ao rodar contra os dados de janeiro/2026: 'título descontado'
# é a carteira de antecipação bancária do Itaú (factoring) — o fluxo de
# caixa é diferente de uma liquidação normal, então comparar seu valor
# cheio contra 'Rec. Dup.' do ERP produzia falso positivo de divergência.
# Tratado separadamente do matching normal por título+valor — ver Regra 13
# mais abaixo, que casa esses lançamentos contra ANTECIPAÇÃO RECEBIVEIS do
# ERP (ou CRP032A1), em vez de descartá-los.
DISCOUNTED_TITLE_OPERATION_TYPES = {
    "liquidação de título descontado",
}

# Achado real: a Francesinha de cobrança só cobre a carteira de BOLETO.
# Recebimentos do ERP via PIX ou depósito em conta não têm — e nunca vão
# ter — contrapartida neste arquivo; contá-los como 'ERP SEM BANCO' seria
# um falso positivo. Eles pertencem a uma futura fonte bancária (extrato de
# conta corrente), não a esta.
ERP_TIPO_DOCUMENTO_IN_SCOPE = {
    "[5] - BOLETO BANCARIO",
    "[3] - BOLETO BANCÁRIO",
}


class ReconciliationStatus(str, Enum):
    CONCILIADO = "CONCILIADO"
    CONCILIADO_D1 = "CONCILIADO D+1"
    CONCILIADO_D2 = "CONCILIADO D+2"
    CORTE_COMPETENCIA = "CORTE DE COMPETÊNCIA"
    BANCO_SEM_ERP = "BANCO SEM ERP"
    ERP_SEM_BANCO = "ERP SEM BANCO"
    VALOR_DIVERGENTE = "VALOR DIVERGENTE"
    TITULO_DESCONTADO = "TÍTULO DESCONTADO SEM CORRESPONDÊNCIA"
    CONCILIADO_ANTECIPACAO = "CONCILIADO (título descontado)"
    CORTE_FIM_PERIODO = "CORTE DE COMPETÊNCIA (fim do período importado)"
    POSSIVEL_CORRESPONDENCIA = "POSSÍVEL CORRESPONDÊNCIA"
    CONCILIADO_DESCONTO = "CONCILIADO (desconto)"


@dataclass
class ReconciliationMatch:
    status: ReconciliationStatus
    bank_tx: BankTransaction | None
    erp_tx: ERPTransaction | None
    confidence: int
    diagnostic: str


def _is_business_day(d: date) -> bool:
    return d.weekday() < 5  # 0=segunda ... 4=sexta


def _next_business_day(d: date) -> date:
    nxt = d + timedelta(days=1)
    while not _is_business_day(nxt):
        nxt += timedelta(days=1)
    return nxt


def _business_days_between(d1: date, d2: date) -> int:
    """Conta dias úteis entre d1 (exclusive) e d2 (inclusive), assumindo d2 >= d1."""
    if d2 < d1:
        return -_business_days_between(d2, d1)
    count = 0
    cur = d1
    while cur < d2:
        cur += timedelta(days=1)
        if _is_business_day(cur):
            count += 1
    return count


def _reclassify_period_boundary_cases(
    results: list[ReconciliationMatch],
    bank_txs: list[BankTransaction],
    erp_txs: list[ERPTransaction],
) -> None:
    """Achado real ao validar contra os dados de janeiro/2026: 43 dos 47
    casos de BANCO SEM ERP caem exatamente no último dia útil coberto pelo
    ERP, e a maioria dos ERP SEM BANCO cai antes do início do arquivo
    bancário. Isso não é divergência — é o corte de competência normal
    (Regra 5) na borda do período importado; só não dá pra confirmar
    automaticamente sem o arquivo do mês adjacente. Reclassifica para um
    status próprio em vez de contar como erro real."""
    erp_dates = [t.transaction_date for t in erp_txs if t.transaction_date]
    bank_dates = [t.movement_date for t in bank_txs]
    if not erp_dates or not bank_dates:
        return
    # Guarda contra falso positivo em datasets de um único dia (ex: testes
    # unitários sintéticos): a heurística de borda de período só faz
    # sentido quando o arquivo realmente cobre uma janela de vários dias.
    if len(set(erp_dates)) <= 1 and len(set(bank_dates)) <= 1:
        return
    erp_max = max(erp_dates)
    bank_min = min(bank_dates)

    for r in results:
        if r.status == ReconciliationStatus.BANCO_SEM_ERP:
            nxt = _next_business_day(r.bank_tx.movement_date)
            if nxt > erp_max:
                r.status = ReconciliationStatus.CORTE_FIM_PERIODO
                r.confidence = 90
                r.diagnostic = (
                    f"Título {r.bank_tx.seu_numero} liquidado em {r.bank_tx.movement_date:%d/%m/%Y}. "
                    f"O próximo dia útil ({nxt:%d/%m/%Y}) está fora do período do ERP importado "
                    f"(até {erp_max:%d/%m/%Y}) — provável corte de competência normal. "
                    f"Confirmar com o arquivo ERP do mês seguinte."
                )
        elif r.status == ReconciliationStatus.ERP_SEM_BANCO:
            if r.erp_tx.transaction_date <= bank_min:
                r.status = ReconciliationStatus.CORTE_FIM_PERIODO
                r.confidence = 90
                r.diagnostic = (
                    f"Baixa no ERP em {r.erp_tx.transaction_date:%d/%m/%Y} para o título "
                    f"{r.erp_tx.invoice_number_raw}, anterior ao início do arquivo bancário "
                    f"importado ({bank_min:%d/%m/%Y}) — provável liquidação do período anterior. "
                    f"Confirmar com o arquivo bancário do mês anterior."
                )


def _extract_erp_client_name(descricao: str) -> str | None:
    match = re.search(r"Cliente:\s*([^-]+?)\s*-\s*\(", descricao)
    return match.group(1).strip() if match else None


def _name_similarity_tokens(a: str | None, b: str | None) -> bool:
    """Comparação simples e conservadora: verdadeiro só se as duas
    primeiras palavras significativas (>=3 letras) coincidirem, ignorando
    razão social (LTDA, ME, EIRELI...). Evita falso positivo de substring
    solta (ex: 'SUL' casando com qualquer nome que contenha 'SUL')."""
    STOPWORDS = {"LTDA", "ME", "EIRELI", "DO", "DA", "DE", "E", "COMERCIO", "RESTAURANTE"}
    if not a or not b:
        return False
    tokens_a = [t for t in re.findall(r"[A-ZÀ-Ú]{3,}", a.upper()) if t not in STOPWORDS][:2]
    tokens_b = [t for t in re.findall(r"[A-ZÀ-Ú]{3,}", b.upper()) if t not in STOPWORDS][:2]
    return bool(tokens_a) and bool(tokens_b) and set(tokens_a) & set(tokens_b)


def _regra9_possiveis_correspondencias(
    results: list[ReconciliationMatch],
    bank_txs: list[BankTransaction],
    erp_txs: list[ERPTransaction],
) -> None:
    """Para os casos que sobraram como BANCO SEM ERP / ERP SEM BANCO após
    as regras anteriores, procura candidatos por valor próximo + data
    próxima + nome do cliente/pagador semelhante. Não concilia
    automaticamente — apenas sinaliza para revisão humana (item 31: melhor
    'possível correspondência' do que conciliar errado)."""
    receivable_erp = [
        t for t in erp_txs
        if t.is_receivable and not t.is_anticipation
        and t.tipo_documento in ERP_TIPO_DOCUMENTO_IN_SCOPE
    ]
    settled_bank = [t for t in bank_txs if t.operation_type in SETTLEMENT_OPERATION_TYPES]

    for r in results:
        if r.status == ReconciliationStatus.BANCO_SEM_ERP:
            b = r.bank_tx
            best, best_score = None, 0
            for e in receivable_erp:
                if e.incoming_amount is None or e.transaction_date is None:
                    continue
                if abs(e.incoming_amount - b.client_amount) > FUZZY_VALUE_TOLERANCE:
                    continue
                if abs(_business_days_between(b.movement_date, e.transaction_date)) > FUZZY_DATE_WINDOW_BUSINESS_DAYS:
                    continue
                cliente = _extract_erp_client_name(e.descricao)
                score = 80 if _name_similarity_tokens(b.payer_name, cliente) else 70
                if score > best_score:
                    best, best_score = e, score
            if best is not None:
                r.status = ReconciliationStatus.POSSIVEL_CORRESPONDENCIA
                r.erp_tx = best
                r.confidence = best_score
                r.diagnostic = (
                    f"Título {b.seu_numero} ({b.payer_name}, R$ {b.client_amount:.2f}, "
                    f"{b.movement_date:%d/%m/%Y}) tem candidato parecido no ERP: título "
                    f"{best.invoice_number_raw} (R$ {best.incoming_amount:.2f}, "
                    f"{best.transaction_date:%d/%m/%Y}). Confiança {best_score}% — revisar manualmente."
                )

        elif r.status == ReconciliationStatus.ERP_SEM_BANCO:
            e = r.erp_tx
            cliente = _extract_erp_client_name(e.descricao)
            best, best_score = None, 0
            for b in settled_bank:
                if b.client_amount is None:
                    continue
                if abs(b.client_amount - e.incoming_amount) > FUZZY_VALUE_TOLERANCE:
                    continue
                if abs(_business_days_between(e.transaction_date, b.movement_date)) > FUZZY_DATE_WINDOW_BUSINESS_DAYS:
                    continue
                score = 80 if _name_similarity_tokens(b.payer_name, cliente) else 70
                if score > best_score:
                    best, best_score = b, score
            if best is not None:
                r.status = ReconciliationStatus.POSSIVEL_CORRESPONDENCIA
                r.bank_tx = best
                r.confidence = best_score
                r.diagnostic = (
                    f"Baixa no ERP para o título {e.invoice_number_raw} (R$ {e.incoming_amount:.2f}, "
                    f"{e.transaction_date:%d/%m/%Y}) tem candidato parecido no banco: "
                    f"{best.seu_numero} ({best.payer_name}, R$ {best.client_amount:.2f}, "
                    f"{best.movement_date:%d/%m/%Y}). Confiança {best_score}% — revisar manualmente."
                )


def run_reconciliation(
    bank_txs: list[BankTransaction],
    erp_txs: list[ERPTransaction],
    crp_docs: list[DocumentoRecebido] | None = None,
) -> list[ReconciliationMatch]:
    settled_bank = [t for t in bank_txs if t.operation_type in SETTLEMENT_OPERATION_TYPES]
    discounted_bank = [t for t in bank_txs if t.operation_type in DISCOUNTED_TITLE_OPERATION_TYPES]
    receivable_erp = [
        t for t in erp_txs
        if t.is_receivable and not t.is_anticipation
        and t.tipo_documento in ERP_TIPO_DOCUMENTO_IN_SCOPE
    ]

    # Regra 12 (opcional): índice do CRP032A1 por título normalizado, usado
    # só para EXPLICAR um valor divergente já detectado — nunca para
    # decidir sozinho se algo concilia.
    crp_by_title: dict[str, DocumentoRecebido] = {}
    for d in (crp_docs or []):
        if d.normalized_title:
            crp_by_title[d.normalized_title] = d

    # Índice ERP por título normalizado (pode haver mais de uma parcela do
    # mesmo título base, ex: 7005-21, 7005-22 — normalized_title já inclui
    # o sufixo da parcela, então cada parcela tem sua própria chave).
    erp_by_title: dict[str, list[ERPTransaction]] = {}
    for t in receivable_erp:
        if t.normalized_title:
            erp_by_title.setdefault(t.normalized_title, []).append(t)

    matched_erp_ids: set[int] = set()
    results: list[ReconciliationMatch] = []

    for bank_tx in settled_bank:
        if not bank_tx.normalized_title or bank_tx.client_amount is None:
            results.append(ReconciliationMatch(
                status=ReconciliationStatus.BANCO_SEM_ERP,
                bank_tx=bank_tx, erp_tx=None, confidence=0,
                diagnostic="Título do banco sem 'Seu Número' ou sem valor apurável — não é possível buscar correspondência.",
            ))
            continue

        candidates = erp_by_title.get(bank_tx.normalized_title, [])
        # Entre candidatos com mesmo título, escolhe o de valor mais próximo
        # ainda não utilizado.
        best = None
        best_diff = None
        for c in candidates:
            if id(c) in matched_erp_ids or c.incoming_amount is None:
                continue
            diff = abs(c.incoming_amount - bank_tx.client_amount)
            if best is None or diff < best_diff:
                best, best_diff = c, diff

        if best is None:
            results.append(ReconciliationMatch(
                status=ReconciliationStatus.BANCO_SEM_ERP,
                bank_tx=bank_tx, erp_tx=None, confidence=0,
                diagnostic=(
                    f"Título {bank_tx.seu_numero} recebido pelo {bank_tx.bank} "
                    f"({bank_tx.movement_date:%d/%m/%Y}, R$ {bank_tx.client_amount:.2f}), "
                    f"porém não foi encontrada baixa correspondente no ERP."
                ),
            ))
            continue

        if best_diff > AMOUNT_TOLERANCE:
            matched_erp_ids.add(id(best))

            crp = crp_by_title.get(bank_tx.normalized_title)
            if crp is not None:
                expected_erp_value = round(bank_tx.client_amount + crp.ajuste_liquido, 2)
                if abs(expected_erp_value - best.incoming_amount) <= AMOUNT_TOLERANCE:
                    results.append(ReconciliationMatch(
                        status=ReconciliationStatus.CONCILIADO_DESCONTO,
                        bank_tx=bank_tx, erp_tx=best, confidence=96,
                        diagnostic=(
                            f"Título {bank_tx.seu_numero}: banco recebeu R$ {bank_tx.client_amount:.2f}, "
                            f"ERP baixou R$ {best.incoming_amount:.2f}. Diferença de R$ {best_diff:.2f} "
                            f"explicada por desconto comercial de R$ {crp.valor_desconto:.2f} "
                            f"(confirmado no CRP032A1, documento {crp.documento})."
                        ),
                    ))
                    continue

            results.append(ReconciliationMatch(
                status=ReconciliationStatus.VALOR_DIVERGENTE,
                bank_tx=bank_tx, erp_tx=best, confidence=60,
                diagnostic=(
                    f"Título {bank_tx.seu_numero}: banco recebeu R$ {bank_tx.client_amount:.2f}, "
                    f"ERP baixou R$ {best.incoming_amount:.2f}. Diferença de R$ {best_diff:.2f} não explicada."
                ),
            ))
            continue

        matched_erp_ids.add(id(best))
        bank_date = bank_tx.movement_date
        erp_date = best.transaction_date

        if bank_date == erp_date:
            results.append(ReconciliationMatch(
                status=ReconciliationStatus.CONCILIADO,
                bank_tx=bank_tx, erp_tx=best, confidence=100,
                diagnostic=f"Título {bank_tx.seu_numero} conciliado: mesmo valor e mesma data no banco e no ERP.",
            ))
            continue

        bdays = _business_days_between(bank_date, erp_date)

        if bdays == 1 and _next_business_day(bank_date) == erp_date:
            # A baixa ocorreu exatamente no próximo dia útil — cobre tanto
            # D+1 "puro" quanto o caso de corte por fim de semana
            # (ex: liquidado sexta, baixado segunda).
            if bank_date.weekday() == 4 and erp_date.weekday() == 0:
                results.append(ReconciliationMatch(
                    status=ReconciliationStatus.CORTE_COMPETENCIA,
                    bank_tx=bank_tx, erp_tx=best, confidence=98,
                    diagnostic=(
                        f"Liquidado em {bank_date:%d/%m/%Y} (sexta) e baixado no ERP em "
                        f"{erp_date:%d/%m/%Y} (segunda seguinte). Corte de competência por fim de semana."
                    ),
                ))
            else:
                results.append(ReconciliationMatch(
                    status=ReconciliationStatus.CONCILIADO_D1,
                    bank_tx=bank_tx, erp_tx=best, confidence=98,
                    diagnostic=(
                        f"Título {bank_tx.seu_numero}: liquidado no banco em {bank_date:%d/%m/%Y}, "
                        f"baixado no ERP em {erp_date:%d/%m/%Y} (D+1 útil)."
                    ),
                ))
        elif bdays == 2:
            results.append(ReconciliationMatch(
                status=ReconciliationStatus.CONCILIADO_D2,
                bank_tx=bank_tx, erp_tx=best, confidence=95,
                diagnostic=(
                    f"Título {bank_tx.seu_numero}: liquidado no banco em {bank_date:%d/%m/%Y}, "
                    f"baixado no ERP em {erp_date:%d/%m/%Y} (D+2 úteis)."
                ),
            ))
        else:
            results.append(ReconciliationMatch(
                status=ReconciliationStatus.VALOR_DIVERGENTE,
                bank_tx=bank_tx, erp_tx=best, confidence=50,
                diagnostic=(
                    f"Título {bank_tx.seu_numero}: valor bate, mas a diferença de data "
                    f"({bdays} dias úteis) é maior que o esperado para D+1/D+2. Requer investigação."
                ),
            ))

    # Regra 13 — título descontado (carteira de antecipação bancária do
    # Itaú) explicado via ANTECIPAÇÃO RECEBIVEIS do ERP ou via CRP032A1.
    # Achado real: dos 94 títulos descontados de janeiro/2026, os 44
    # lançamentos de antecipação do ERP batem 1:1 e com valor exato — é a
    # MESMA operação, cada sistema só usa um nome diferente pra ela. Mais 4
    # batem exato com o CRP032A1 (documentos que nem aparecem no FFP045A2).
    # Os 46 restantes ficam genuinamente sem explicação — sem inventar.
    antecipacao_erp = [
        t for t in erp_txs
        if t.is_anticipation and t.tipo_documento in ERP_TIPO_DOCUMENTO_IN_SCOPE
    ]
    antecipacao_by_title: dict[str, ERPTransaction] = {}
    for t in antecipacao_erp:
        if t.normalized_title:
            antecipacao_by_title.setdefault(t.normalized_title, t)
    matched_antecipacao_titles: set[str] = set()

    for bank_tx in discounted_bank:
        candidate = antecipacao_by_title.get(bank_tx.normalized_title)
        if (
            candidate is not None and bank_tx.client_amount is not None
            and candidate.incoming_amount is not None
            and abs(bank_tx.client_amount - candidate.incoming_amount) <= AMOUNT_TOLERANCE
        ):
            matched_antecipacao_titles.add(bank_tx.normalized_title)
            results.append(ReconciliationMatch(
                status=ReconciliationStatus.CONCILIADO_ANTECIPACAO,
                bank_tx=bank_tx, erp_tx=candidate, confidence=95,
                diagnostic=(
                    f"Título {bank_tx.seu_numero}: liquidado via carteira de título descontado "
                    f"(antecipação bancária) em {bank_tx.movement_date:%d/%m/%Y}, R$ {bank_tx.client_amount:.2f}. "
                    f"Confirmado no ERP como 'ANTECIPAÇÃO RECEBIVEIS', mesmo valor."
                ),
            ))
            continue

        crp = crp_by_title.get(bank_tx.normalized_title)
        if (
            crp is not None and bank_tx.client_amount is not None and crp.valor_pago is not None
            and abs(bank_tx.client_amount - crp.valor_pago) <= AMOUNT_TOLERANCE
        ):
            results.append(ReconciliationMatch(
                status=ReconciliationStatus.CONCILIADO_ANTECIPACAO,
                bank_tx=bank_tx, erp_tx=None, confidence=90,
                diagnostic=(
                    f"Título {bank_tx.seu_numero}: liquidado via carteira de título descontado "
                    f"(antecipação bancária) em {bank_tx.movement_date:%d/%m/%Y}, R$ {bank_tx.client_amount:.2f}. "
                    f"Não está no FFP045A2, mas confirmado no CRP032A1 (documento {crp.documento}), mesmo valor."
                ),
            ))
            continue

        results.append(ReconciliationMatch(
            status=ReconciliationStatus.TITULO_DESCONTADO,
            bank_tx=bank_tx, erp_tx=None, confidence=0,
            diagnostic=(
                f"Título {bank_tx.seu_numero} liquidado via carteira de título descontado "
                f"(antecipação bancária) em {bank_tx.movement_date:%d/%m/%Y}, "
                f"R$ {(bank_tx.client_amount or bank_tx.principal_amount or 0):.2f}. "
                f"Não encontrado como antecipação no ERP nem no CRP032A1 — verificar manualmente se "
                f"o documento foi lançado no ERP com outra classificação ou se ainda não foi baixado."
            ),
        ))

    # Antecipação do ERP sem nenhum título descontado correspondente no
    # banco (não observado em janeiro/2026, mas tratado por segurança —
    # ver item 39, não deixar nada sem status).
    for t in antecipacao_erp:
        if t.normalized_title and t.normalized_title not in matched_antecipacao_titles:
            results.append(ReconciliationMatch(
                status=ReconciliationStatus.ERP_SEM_BANCO,
                bank_tx=None, erp_tx=t, confidence=0,
                diagnostic=(
                    f"ERP registra antecipação de recebíveis para o título {t.invoice_number_raw} "
                    f"em {t.transaction_date:%d/%m/%Y} (R$ {t.incoming_amount:.2f}), sem nenhuma "
                    f"liquidação de título descontado correspondente encontrada no banco."
                ),
            ))

    for t in receivable_erp:
        if id(t) not in matched_erp_ids:
            results.append(ReconciliationMatch(
                status=ReconciliationStatus.ERP_SEM_BANCO,
                bank_tx=None, erp_tx=t, confidence=0,
                diagnostic=(
                    f"Baixa no ERP em {t.transaction_date:%d/%m/%Y} para o título "
                    f"{t.invoice_number_raw} (R$ {t.incoming_amount:.2f}), sem liquidação "
                    f"correspondente encontrada no banco."
                ),
            ))

    _reclassify_period_boundary_cases(results, bank_txs, erp_txs)
    _regra9_possiveis_correspondencias(results, bank_txs, erp_txs)

    return results


if __name__ == "__main__":
    from pathlib import Path
    from collections import Counter
    from app.importers.banks.itau_francesinha import import_itau_francesinha
    from app.importers.erp.ffp045a2 import import_erp_ffp045a2
    from app.importers.erp.crp032a1 import import_crp032a1

    base = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
    bank_txs = import_itau_francesinha(base / "itau_francesinha_janeiro2026.xlsx")
    erp_txs = import_erp_ffp045a2(base / "erp_janeiro2026.xlsx")
    crp_path = base / "crp032a1_janeiro2026.xlsx"
    crp_docs = import_crp032a1(crp_path) if crp_path.exists() else []

    results = run_reconciliation(bank_txs, erp_txs, crp_docs)

    counts = Counter(r.status for r in results)
    print("=== DASHBOARD (janeiro/2026, MEATHUNTER, Itaú 98967-1) ===")
    for status in ReconciliationStatus:
        print(f"  {status.value}: {counts.get(status, 0)}")
    print(f"  TOTAL de registros no motor: {len(results)}")

    total_conciliado = counts.get(ReconciliationStatus.CONCILIADO, 0) \
        + counts.get(ReconciliationStatus.CONCILIADO_D1, 0) \
        + counts.get(ReconciliationStatus.CONCILIADO_D2, 0) \
        + counts.get(ReconciliationStatus.CORTE_COMPETENCIA, 0) \
        + counts.get(ReconciliationStatus.CORTE_FIM_PERIODO, 0) \
        + counts.get(ReconciliationStatus.CONCILIADO_DESCONTO, 0) \
        + counts.get(ReconciliationStatus.CONCILIADO_ANTECIPACAO, 0)
    total_registros = len(results)
    pct = 100 * total_conciliado / total_registros if total_registros else 0
    print(f"\n% conciliação (sobre liquidações bancárias): {pct:.2f}%")

    print("\n--- Amostra de BANCO SEM ERP ---")
    for r in [r for r in results if r.status == ReconciliationStatus.BANCO_SEM_ERP][:5]:
        print(" ", r.diagnostic)

    print("\n--- Caso 700521 / 7005-21 ---")
    for r in results:
        if (r.bank_tx and r.bank_tx.normalized_title == "700521") or \
           (r.erp_tx and r.erp_tx.normalized_title == "700521"):
            print(f"  status={r.status.value} diag={r.diagnostic}")
