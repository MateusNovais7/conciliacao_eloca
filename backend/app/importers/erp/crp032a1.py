"""
Importador — Relatório ERP CRP032A1 (Relação de Documentos Recebidos).

Achado real (título 34238-21, janeiro/2026): o FFP045A2 mostra a baixa já
líquida (R$ 3.437,98), sem explicar por que ela é menor que o principal
registrado no banco (R$ 3.725,84). O CRP032A1 tem a resposta: 'Valor
Desconto' = R$ 287,86, e 3.725,84 - 287,86 = 3.437,98 exatamente.

Ou seja: este relatório NÃO substitui o FFP045A2 — ele COMPLEMENTA,
explicando divergências de valor que seriam desconto comercial em vez de
erro real. Usado pelo motor para reclassificar 'VALOR DIVERGENTE' em
'CONCILIADO (desconto)' quando o desconto explica a diferença exatamente.

Formato real observado (arquivo de exemplo, uma linha de dados):
  Colunas relevantes: Documento (mesmo identificador do 'Fatura/Seq' do
  FFP045A2 — normaliza para o mesmo valor), Valor Emissão, Impostos
  Retidos, Valor Desconto, Valor Abatimento, Valor Juros, Valor Multa,
  Valor Pago. A linha final da planilha é um total ('Valor Total' na
  coluna de Data Crédito) — não é um documento, precisa ser ignorada.

  Conferido: Valor Pago = Valor Emissão - Impostos Retidos - Valor
  Desconto - Valor Abatimento + Valor Juros + Valor Multa (convenção
  contábil padrão: descontos/impostos reduzem, juros/multa aumentam).

MESMO BUG DE STYLESHEET do FFP045A2 — reparado da mesma forma via
LibreOffice headless (ver _repair_stylesheet_if_needed, duplicado aqui
propositalmente para manter os importadores independentes entre si,
conforme a arquitetura pluggável do item 2 do escopo).
"""
from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from app.reconciliation.normalization import normalize_title
from app.reconciliation.parsing import parse_brl_currency, parse_erp_date

EXPECTED_COLUMNS = [
    "Local", "Nota", "CentroCusto", "TipoReceita", "Banco", "Agencia", "CC", "OS",
    "Contrato", "TipoContrato", "VigenciaInicio", "VigenciaFim", "Fatura", "NFSe",
    "Documento", "Cliente", "CnpjCpf", "Grupo", "TipoBaixa", "Representante",
    "DataEmissao", "DataVencto", "DataPagto", "DataCredito", "ValorEmissao",
    "ImpostosRetidos", "ValorDesconto", "ValorAbatimento", "ValorJuros",
    "ValorMulta", "SaldoNaData", "ValorPago", "MesAno",
]


@dataclass
class DocumentoRecebido:
    documento: str
    normalized_title: str | None
    cliente: str | None
    data_pagamento: date | None
    valor_emissao: float | None
    impostos_retidos: float
    valor_desconto: float
    valor_abatimento: float
    valor_juros: float
    valor_multa: float
    valor_pago: float | None
    raw_row: dict = field(default_factory=dict)

    @property
    def ajuste_liquido(self) -> float:
        """Quanto se soma (ou subtrai, se negativo) ao valor bruto do
        título para chegar no valor efetivamente recebido — usado pelo
        motor para explicar (não forçar) divergências de valor."""
        return round(
            -self.impostos_retidos - self.valor_desconto - self.valor_abatimento
            + self.valor_juros + self.valor_multa,
            2,
        )


def _repair_stylesheet_if_needed(path: Path) -> Path:
    try:
        pd.ExcelFile(path)
        return path
    except Exception:
        pass
    tmp_dir = Path(tempfile.mkdtemp(prefix="crp_repair_"))
    result = subprocess.run(
        ["soffice", "--headless", "--convert-to", "xlsx", "--outdir", str(tmp_dir), str(path)],
        capture_output=True, text=True, timeout=90,
    )
    repaired = tmp_dir / path.name
    if result.returncode != 0 or not repaired.exists():
        raise RuntimeError(
            f"Não foi possível reparar a stylesheet do arquivo CRP032A1 '{path.name}'. "
            f"Detalhe técnico: {result.stderr}"
        )
    return repaired


def import_crp032a1(path: str | Path) -> list[DocumentoRecebido]:
    readable_path = _repair_stylesheet_if_needed(Path(path))
    raw = pd.read_excel(readable_path, header=0)
    raw.columns = EXPECTED_COLUMNS[:len(raw.columns)]

    documentos: list[DocumentoRecebido] = []
    for _, row in raw.iterrows():
        documento = row.get("Documento")
        if pd.isna(documento):
            continue  # linha de total ou vazia — não é um documento real

        documentos.append(DocumentoRecebido(
            documento=str(documento).strip(),
            normalized_title=normalize_title(documento),
            cliente=str(row.get("Cliente")).strip() if pd.notna(row.get("Cliente")) else None,
            data_pagamento=parse_erp_date(row.get("DataPagto")),
            valor_emissao=parse_brl_currency(row.get("ValorEmissao")),
            impostos_retidos=parse_brl_currency(row.get("ImpostosRetidos")) or 0.0,
            valor_desconto=parse_brl_currency(row.get("ValorDesconto")) or 0.0,
            valor_abatimento=parse_brl_currency(row.get("ValorAbatimento")) or 0.0,
            valor_juros=parse_brl_currency(row.get("ValorJuros")) or 0.0,
            valor_multa=parse_brl_currency(row.get("ValorMulta")) or 0.0,
            valor_pago=parse_brl_currency(row.get("ValorPago")),
            raw_row=row.to_dict(),
        ))
    return documentos


if __name__ == "__main__":
    fixture = Path(__file__).resolve().parents[3] / "tests" / "fixtures_novos" / "fixed" / "crp032a1_original.xlsx"
    docs = import_crp032a1(fixture)
    print(f"Documentos importados: {len(docs)}")
    for d in docs:
        print(f"  {d.documento} (norm={d.normalized_title}) emissao={d.valor_emissao} "
              f"desconto={d.valor_desconto} pago={d.valor_pago} ajuste_liquido={d.ajuste_liquido}")
        esperado = round((d.valor_emissao or 0) + d.ajuste_liquido, 2)
        print(f"    conferindo: emissao + ajuste_liquido = {esperado} (esperado bater com valor_pago={d.valor_pago})")
        assert abs(esperado - (d.valor_pago or 0)) < 0.01, "fórmula não bateu — revisar antes de usar no motor"
    print("Fórmula confirmada contra o caso real.")
