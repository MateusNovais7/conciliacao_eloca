"""
Importador — Relatório ERP FFP045A2 (extrato financeiro por conta).

Formato real observado (MEATHUNTER, janeiro/2026):
  - Uma única aba, extrato contínuo em ordem cronológica com saldo corrente.
  - Linhas de separador ('Descrição' = 'Saldo em DD/MM/AAAA') marcam o fim
    de cada dia — são informativas (saldo do dia), não transações.
  - Coluna 'Data' vem como 'DD/MM/AAAA <abrev. dia da semana>' (ex: '05/01/2026 Seg').
  - Coluna 'Fatura/Seq' é o identificador do título (ex: '7005-21').
  - Coluna 'Tipo' classifica a linha: 'Rec. Dup.' (recebimento de duplicata
    — é isso que compara com o banco), 'Pagamento', 'Despesa', 'Transferência',
    'Receita'. Só 'Rec. Dup.' entra na conciliação bancária.
  - Coluna 'Descrição' contém 'Tipo Baixa: ANTECIPAÇÃO RECEBIVEIS' quando o
    título é uma antecipação de recebíveis (Regra 6) — não deve ser
    misturado com recebimentos normais.
  - Valores em 'Entrada'/'Saída' vêm em formato brasileiro como texto
    ('1.579,39'), não como número.

BUG CONHECIDO DO ARQUIVO ORIGINAL: a stylesheet do .xlsx exportado pelo ERP
vem corrompida (openpyxl e pandas falham com
'TypeError: expected <class Fill>' ao tentar ler). Contornamos convertendo
o arquivo via LibreOffice headless antes de processar — isso reescreve a
stylesheet sem alterar os dados. Fica registrado aqui porque é um problema
conhecido do exportador do ERP, não do nosso importador.
"""
from __future__ import annotations

import hashlib
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from app.reconciliation.normalization import normalize_title
from app.reconciliation.parsing import parse_brl_currency, parse_erp_date

EXPECTED_COLUMNS = [
    "Local", "Data", "Codigo", "c3", "c4", "c5", "c6",
    "TipoDocumento", "Contrato", "FaturaSeq", "Conciliado",
    "Tipo", "NotaFiscal", "Descricao", "Entrada", "Saida", "Saldo",
]

ANTECIPACAO_MARKER = "ANTECIPAÇÃO RECEBIVEIS"
RECEIVABLE_TIPO = "Rec. Dup."


@dataclass
class ERPTransaction:
    account_local: str
    transaction_date: date
    invoice_number_raw: str          # ex: '7005-21'
    normalized_title: str | None
    tipo: str | None                 # 'Rec. Dup.', 'Pagamento', ...
    tipo_documento: str | None       # '[5] - BOLETO BANCARIO', '[2] - PIX', ...
    nota_fiscal: str | None
    descricao: str
    incoming_amount: float | None    # coluna 'Entrada'
    outgoing_amount: float | None    # coluna 'Saída'
    balance: float | None
    is_anticipation: bool
    raw_row: dict = field(default_factory=dict)

    @property
    def is_receivable(self) -> bool:
        """Só recebimentos de duplicata (Rec. Dup.) entram na conciliação
        com o banco."""
        return self.tipo == RECEIVABLE_TIPO


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repair_stylesheet_if_needed(path: Path) -> Path:
    """Tenta ler o arquivo; se a stylesheet estiver corrompida, converte via
    LibreOffice headless para um arquivo temporário reparado."""
    try:
        pd.ExcelFile(path)
        return path
    except Exception:
        pass

    tmp_dir = Path(tempfile.mkdtemp(prefix="erp_repair_"))
    result = subprocess.run(
        ["soffice", "--headless", "--convert-to", "xlsx", "--outdir", str(tmp_dir), str(path)],
        capture_output=True, text=True, timeout=90,
    )
    repaired = tmp_dir / path.name
    if result.returncode != 0 or not repaired.exists():
        raise RuntimeError(
            f"Não foi possível reparar a stylesheet do arquivo ERP '{path.name}'. "
            f"Verifique se o arquivo não foi corrompido no download. Detalhe técnico: {result.stderr}"
        )
    return repaired


def import_erp_ffp045a2(path: str | Path) -> list[ERPTransaction]:
    original_path = Path(path)
    readable_path = _repair_stylesheet_if_needed(original_path)

    raw = pd.read_excel(readable_path, header=0)
    raw.columns = EXPECTED_COLUMNS[:len(raw.columns)]

    transactions: list[ERPTransaction] = []

    for _, row in raw.iterrows():
        descricao = row.get("Descricao")
        descricao_str = "" if pd.isna(descricao) else str(descricao)

        # Linha separadora de saldo diário — não é uma transação.
        if descricao_str.startswith("Saldo em"):
            continue

        transaction_date = parse_erp_date(row.get("Data"))
        invoice_raw = row.get("FaturaSeq")
        if pd.isna(invoice_raw) and transaction_date is None:
            continue  # linha totalmente vazia / de formatação

        invoice_raw = None if pd.isna(invoice_raw) else str(invoice_raw).strip()
        tipo = row.get("Tipo")
        tipo = None if pd.isna(tipo) else str(tipo).strip()

        transactions.append(ERPTransaction(
            account_local=str(row.get("Local", "")).strip() if pd.notna(row.get("Local")) else "",
            transaction_date=transaction_date,
            invoice_number_raw=invoice_raw,
            normalized_title=normalize_title(invoice_raw),
            tipo=tipo,
            tipo_documento=str(row.get("TipoDocumento")).strip() if pd.notna(row.get("TipoDocumento")) else None,
            nota_fiscal=str(row.get("NotaFiscal")).strip() if pd.notna(row.get("NotaFiscal")) else None,
            descricao=descricao_str,
            incoming_amount=parse_brl_currency(row.get("Entrada")),
            outgoing_amount=parse_brl_currency(row.get("Saida")),
            balance=parse_brl_currency(row.get("Saldo")),
            is_anticipation=ANTECIPACAO_MARKER in descricao_str.upper(),
            raw_row=row.to_dict(),
        ))

    return transactions


if __name__ == "__main__":
    fixture = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "erp_janeiro2026.xlsx"
    txs = import_erp_ffp045a2(fixture)
    print(f"Total de linhas de transação importadas: {len(txs)}")
    print(f"Hash do arquivo original: {_file_hash(fixture)[:16]}...")

    receivable = [t for t in txs if t.is_receivable]
    print(f"Recebimentos de duplicata (Rec. Dup.): {len(receivable)}")

    anticip = [t for t in receivable if t.is_anticipation]
    print(f"...dos quais antecipação de recebíveis: {len(anticip)}")
    for t in anticip[:3]:
        print(f"  {t.transaction_date} título={t.invoice_number_raw} valor={t.incoming_amount}")

    case = [t for t in receivable if t.normalized_title == normalize_title("7005-21")]
    print(f"\nCaso 7005-21 (todas as parcelas do mesmo título base 7005): {len(case)}")
    for t in case:
        print(f"  data={t.transaction_date} titulo={t.invoice_number_raw} valor={t.incoming_amount}")

    negative_balances = [t for t in txs if t.balance is not None and t.balance < 0]
    print(f"\nLinhas com saldo negativo no período: {len(negative_balances)}")
