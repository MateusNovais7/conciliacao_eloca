"""
Importador — Relatório ERP FTP050 (Relação de NF Emitidas).

Usado para UM CASO ESPECÍFICO: recuperar documentos a receber que foram
apagados do ERP a pedido do cliente (ver app/services/recovery_service.py).
Quando isso acontece, o título vira 'TÍTULO DESCONTADO SEM CORRESPONDÊNCIA'
no motor — este relatório permite descobrir de qual Local e para qual
Cliente o documento deveria ser recriado, cruzando pelo número da NF
(extraído do 'Seu Número' da Francesinha).

Formato real observado (MEATHUNTER, exportado em 3 arquivos por limite do
ERP de 6 meses por consulta — Jan/2025 até Set/2026):
  Colunas relevantes: Local (texto: 'MEAT HUNTER', 'MEAT HUNTER SP',
  'MEAT BARRA', 'MEAT HUNTER RJ2'), Data de Emissão, Nota Fiscal, Cliente
  (ID numérico), Razão Social, CNPJ/CPF, Total.

  O relatório pode ter MÚLTIPLOS arquivos para o mesmo período (um por
  exportação de até 6 meses) — o importador aceita isso naturalmente
  chamando import_ftp050() uma vez por arquivo e concatenando os
  resultados no serviço, sem duplicar (cada arquivo tem hash próprio).

MESMO BUG DE STYLESHEET do FFP045A2/CRP032A1 — reparado da mesma forma.

MAPEAMENTO DE LOCAL — específico do cliente MEATHUNTER, informado
diretamente por eles (não inferido dos dados):
  0 - MEAT HUNTER    (RJ)
  2 - MEAT HUNTER SP (SP)
  4 - MEAT BARRA     (RJ)
  5 - MEAT HUNTER RJ2 (RJ)
Se um Local novo aparecer fora deste mapeamento, o importador NÃO inventa
um ID — deixa None e sinaliza para investigação (ver local_id=None).
"""
from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from app.reconciliation.parsing import parse_brl_currency, parse_erp_date

EXPECTED_COLUMNS = [
    "Local", "DataEmissao", "NotaFiscal", "Serie", "Especie", "CFOP", "Pedido",
    "TipoOS", "OS", "Origem", "Proposta", "Cliente", "RazaoSocial", "CnpjCpf",
    "Municipio", "UF", "CondicaoPagamento", "CodRepresentante", "Representante",
    "Motorista", "Item", "Produto", "Descricao", "Lote", "NrSerie", "Grupo",
    "Grupo2", "CodTributacao", "CstCsosn", "Fonte", "NCM", "Quantidade",
    "PrecoUnitario", "ValorDesconto", "ValorFrete", "EncargosFinanc",
    "ValorSeguro", "ValICMS", "PercICMS", "ValICMSDif", "ValICMSSTrib",
    "ValICMSZFranca", "ValIPI", "PercIPI", "ValPartilha", "ValPobreza",
    "ValFCPST", "ValPIS", "ValCofins", "Total",
]

# Achado real, informado pelo cliente — ver docstring do módulo.
LOCAL_IDS: dict[str, int] = {
    "MEAT HUNTER": 0,
    "MEAT HUNTER SP": 2,
    "MEAT BARRA": 4,
    "MEAT HUNTER RJ2": 5,
}


@dataclass
class NotaFiscalEmitida:
    local_nome: str
    local_id: int | None
    data_emissao: date | None
    nota_fiscal: str
    cliente_id: str | None
    razao_social: str | None
    cnpj_cpf: str | None
    total: float | None
    raw_row: dict = field(default_factory=dict)


def _repair_stylesheet_if_needed(path: Path) -> Path:
    try:
        pd.ExcelFile(path)
        return path
    except Exception:
        pass
    tmp_dir = Path(tempfile.mkdtemp(prefix="ftp050_repair_"))
    result = subprocess.run(
        ["soffice", "--headless", "--convert-to", "xlsx", "--outdir", str(tmp_dir), str(path)],
        capture_output=True, text=True, timeout=180,
    )
    repaired = tmp_dir / path.name
    if result.returncode != 0 or not repaired.exists():
        raise RuntimeError(
            f"Não foi possível reparar a stylesheet do arquivo FTP050 '{path.name}'. "
            f"Detalhe técnico: {result.stderr}"
        )
    return repaired


def import_ftp050(path: str | Path) -> list[NotaFiscalEmitida]:
    readable_path = _repair_stylesheet_if_needed(Path(path))
    raw = pd.read_excel(readable_path, header=0)
    raw.columns = EXPECTED_COLUMNS[:len(raw.columns)]

    notas: list[NotaFiscalEmitida] = []
    for _, row in raw.iterrows():
        nf = row.get("NotaFiscal")
        if pd.isna(nf):
            continue

        local_nome = row.get("Local")
        local_nome = None if pd.isna(local_nome) else str(local_nome).strip()

        notas.append(NotaFiscalEmitida(
            local_nome=local_nome or "",
            local_id=LOCAL_IDS.get(local_nome) if local_nome else None,
            data_emissao=parse_erp_date(row.get("DataEmissao")),
            nota_fiscal=str(nf).strip(),
            cliente_id=str(row.get("Cliente")).strip() if pd.notna(row.get("Cliente")) else None,
            razao_social=str(row.get("RazaoSocial")).strip() if pd.notna(row.get("RazaoSocial")) else None,
            cnpj_cpf=str(row.get("CnpjCpf")).strip() if pd.notna(row.get("CnpjCpf")) else None,
            total=parse_brl_currency(row.get("Total")),
            raw_row=row.to_dict(),
        ))
    return notas
