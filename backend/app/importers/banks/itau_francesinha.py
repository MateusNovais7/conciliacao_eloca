"""
Importador — Extrato de Movimentação de Cobrança Itaú (Francesinha).

Formato real observado (conta 6157/98967-1, janeiro/2026):
  - Um arquivo .xlsx com uma aba POR DIA ÚTIL (nome da aba = DD-MM-AAAA).
  - Cada aba tem 3 blocos: resumo de movimentação, resumo financeiro,
    e a tabela 'Movimentação Detalhada' (cabeçalho variável de posição).
  - Cada título liquidado aparece como 1 a 3 linhas EMPILHADAS que
    compartilham o mesmo 'Nosso Número':
        linha 1: a operação principal (liquidação / entrada / baixa / ...)
        linha 2 (opcional): 'tarifa de cobrança', Operações Valor = -1
        linha 3 (opcional): 'juros', Operações Valor = valor do juros
  - Essas linhas precisam ser agrupadas em UM registro por título antes de
    seguir para o motor de conciliação. Tratá-las como linhas independentes
    quebraria a Regra 3 (juros) e contaria tarifas como títulos.

Isso NÃO tenta ser um parser genérico de qualquer banco — é especificamente
o formato Itaú. Novos bancos ganham seu próprio módulo em importers/banks/,
implementando a mesma interface (ver importers/base.py, a criar).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from app.reconciliation.normalization import normalize_title

DETAIL_HEADER_MARKERS = {
    "Carteira", "Pagador", "Tipo", "Nosso Número", "Seu Número",
}


@dataclass
class BankTransaction:
    bank: str
    account: str
    movement_date: date
    nosso_numero: str
    seu_numero: str | None
    normalized_title: str | None
    payer_name: str | None
    operation_type: str | None  # tipo da linha principal: liquidação, entrada, baixa, ...
    principal_amount: float | None  # 'Valor Inicial' da linha principal
    fee_amount: float          # soma das linhas 'tarifa de cobrança' (negativo = desconto)
    interest_amount: float     # soma das linhas 'juros'
    final_amount: float | None  # 'Valor Final' da linha principal (líquido no banco)
    source_sheet: str
    raw_rows: list[dict] = field(default_factory=list)

    @property
    def client_amount(self) -> float | None:
        """Regra 3: valor que o cliente efetivamente pagou = principal + juros
        (a tarifa bancária NÃO reduz o valor pago pelo cliente)."""
        if self.principal_amount is None:
            return None
        return round(self.principal_amount + self.interest_amount, 2)


def _find_detail_header_row(df: pd.DataFrame) -> int | None:
    for idx, row in df.iterrows():
        values = {str(v).strip() for v in row.tolist() if pd.notna(v)}
        if DETAIL_HEADER_MARKERS.issubset(values):
            return idx
    return None


def _parse_sheet_date(sheet_name: str) -> date:
    return datetime.strptime(sheet_name, "%d-%m-%Y").date()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_itau_francesinha(path: str | Path, bank: str = "Itaú") -> list[BankTransaction]:
    path = Path(path)
    xls = pd.ExcelFile(path)

    transactions: list[BankTransaction] = []

    for sheet_name in xls.sheet_names:
        try:
            movement_date = _parse_sheet_date(sheet_name)
        except ValueError:
            # Aba que não representa um dia de movimentação (ex: 'Resumo').
            # Não interrompe a importação inteira por uma aba inesperada.
            continue

        raw = pd.read_excel(xls, sheet_name=sheet_name, header=None)
        header_idx = _find_detail_header_row(raw)
        if header_idx is None:
            continue

        headers = [str(h).strip() if pd.notna(h) else f"col{i}" for i, h in enumerate(raw.iloc[header_idx])]
        detail = raw.iloc[header_idx + 1:].copy()
        detail.columns = headers
        detail = detail.dropna(how="all")

        # Conta e agência vêm do cabeçalho da aba, não da tabela detalhada.
        account = str(raw.iloc[1, 1]).strip() if pd.notna(raw.iloc[1, 1]) else ""

        # Agrupa linhas empilhadas por Nosso Número, preservando a ordem de
        # primeira ocorrência.
        groups: dict[str, list[dict]] = {}
        order: list[str] = []
        for _, row in detail.iterrows():
            nosso = row.get("Nosso Número")
            if pd.isna(nosso):
                continue
            nosso = str(nosso).strip()
            groups.setdefault(nosso, [])
            if nosso not in order:
                order.append(nosso)
            groups[nosso].append(row.to_dict())

        for nosso in order:
            rows = groups[nosso]
            main_row = None
            fee_total = 0.0
            interest_total = 0.0
            for r in rows:
                desc = str(r.get("Descrição de Operações", "")).strip().lower()
                op_valor = r.get("Operações Valor (R$)")
                op_valor = 0.0 if pd.isna(op_valor) or op_valor == "-" else float(op_valor)
                if desc == "tarifa de cobrança":
                    fee_total += op_valor
                elif desc == "juros":
                    interest_total += op_valor
                elif main_row is None and pd.notna(r.get("Pagador")):
                    main_row = r

            if main_row is None:
                # Só existem linhas de tarifa/juros para esse Nosso Número
                # sem uma linha principal identificada nesta aba — mantém
                # bruto para investigação manual em vez de descartar.
                main_row = rows[0]

            seu_numero = main_row.get("Seu Número")
            seu_numero = None if pd.isna(seu_numero) else str(seu_numero).strip()

            valor_inicial = main_row.get("Valor Inicial (R$)")
            valor_inicial = None if pd.isna(valor_inicial) else float(valor_inicial)

            valor_final = main_row.get("Valor Final (R$)")
            valor_final = None if pd.isna(valor_final) else float(valor_final)

            payer = main_row.get("Pagador")
            payer = None if pd.isna(payer) else str(payer).strip()

            op_type = main_row.get("Descrição de Operações")
            op_type = None if pd.isna(op_type) else str(op_type).strip()

            transactions.append(BankTransaction(
                bank=bank,
                account=account,
                movement_date=movement_date,
                nosso_numero=nosso,
                seu_numero=seu_numero,
                normalized_title=normalize_title(seu_numero),
                payer_name=payer,
                operation_type=op_type,
                principal_amount=valor_inicial,
                fee_amount=round(fee_total, 2),
                interest_amount=round(interest_total, 2),
                final_amount=valor_final,
                source_sheet=sheet_name,
                raw_rows=rows,
            ))

    return transactions


if __name__ == "__main__":
    fixture = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "itau_francesinha_janeiro2026.xlsx"
    txs = import_itau_francesinha(fixture)
    print(f"Total de registros (Nosso Número) importados: {len(txs)}")
    print(f"Hash do arquivo: {_file_hash(fixture)[:16]}...")

    by_op = {}
    for t in txs:
        by_op[t.operation_type] = by_op.get(t.operation_type, 0) + 1
    print("Por tipo de operação:")
    for op, count in sorted(by_op.items(), key=lambda x: -x[1]):
        print(f"  {op}: {count}")

    # Caso real: título 700521 / 7005-21, valor 1.579,39
    case = [t for t in txs if t.normalized_title == normalize_title("7005-21")]
    print(f"\nCaso 700521 encontrado: {len(case)} registro(s)")
    for t in case:
        print(f"  seu_numero={t.seu_numero} normalized={t.normalized_title} "
              f"principal={t.principal_amount} tarifa={t.fee_amount} final={t.final_amount} "
              f"data={t.movement_date}")

    # Caso real: juros — título 681721, principal 735,73 + juros 55,17 = 790,90
    case2 = [t for t in txs if t.normalized_title == normalize_title("681721")]
    print(f"\nCaso juros (681721) encontrado: {len(case2)} registro(s)")
    for t in case2:
        print(f"  principal={t.principal_amount} juros={t.interest_amount} "
              f"tarifa={t.fee_amount} valor_cliente={t.client_amount}")
