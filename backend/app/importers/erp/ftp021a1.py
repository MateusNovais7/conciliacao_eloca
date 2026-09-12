"""
Importador — Relatório ERP FTP021A1 (Pedidos / Notas Fiscais).

Usado para complementar a recuperação de documentos apagados (ver
app/services/recovery_service.py) com o campo Representante, que o
FTP050 não tem.

Formato real observado (MEATHUNTER, ~48 mil pedidos):
  Colunas relevantes: Local, Pedido, Nota Fiscal (formato composto:
  'NFE-{numero}/{serie}{data emissão DD/MM/AAAA}' sem separador entre a
  série e a data — ex: 'NFE-17962/102/01/2025' = NF 17962, série 1,
  emitida em 02/01/2025), Cliente (formato 'ID - RAZÃO SOCIAL [UF]'),
  Representante (formato 'NOME [ID]').

Confirmado nos dois casos reais já validados contra o FTP050:
  NF 34006 -> Cliente 1433 (AVENIDA RIO BRASA...), Representante 7
  NF 6892  -> Cliente 1642 (BAMBUA...), Representante 71
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from app.reconciliation.parsing import parse_erp_date

NF_PATTERN = re.compile(r"NFE-(\d+)/(\d+)(\d{2}/\d{2}/\d{4})")
CLIENTE_PATTERN = re.compile(r"^(\d+)\s*-\s*(.+?)\s*\[([A-Z]{2})\]$")
REPRESENTANTE_PATTERN = re.compile(r"^(.*?)\s*\[(\d+)\]$")


@dataclass
class PedidoNotaFiscal:
    local: str
    pedido: str | None
    nota_fiscal: str
    serie: str | None
    data_emissao: date | None
    cliente_id: str | None
    razao_social: str | None
    representante_id: str | None
    representante_nome: str | None
    raw_row: dict = field(default_factory=dict)


def _repair_stylesheet_if_needed(path: Path) -> Path:
    try:
        pd.ExcelFile(path)
        return path
    except Exception:
        pass
    tmp_dir = Path(tempfile.mkdtemp(prefix="ftp021_repair_"))
    result = subprocess.run(
        ["soffice", "--headless", "--convert-to", "xlsx", "--outdir", str(tmp_dir), str(path)],
        capture_output=True, text=True, timeout=240,
    )
    repaired = tmp_dir / path.name
    if result.returncode != 0 or not repaired.exists():
        raise RuntimeError(
            f"Não foi possível reparar a stylesheet do arquivo FTP021A1 '{path.name}'. "
            f"Detalhe técnico: {result.stderr}"
        )
    return repaired


def _parse_cliente(raw: str | None) -> tuple[str | None, str | None]:
    if not raw or pd.isna(raw):
        return None, None
    m = CLIENTE_PATTERN.match(str(raw).strip())
    if not m:
        return None, str(raw).strip()
    return m.group(1), m.group(2).strip()


def _parse_representante(raw: str | None) -> tuple[str | None, str | None]:
    if not raw or pd.isna(raw):
        return None, None
    m = REPRESENTANTE_PATTERN.match(str(raw).strip())
    if not m:
        return None, str(raw).strip()
    return m.group(2), m.group(1).strip()


def import_ftp021a1(path: str | Path) -> list[PedidoNotaFiscal]:
    readable_path = _repair_stylesheet_if_needed(Path(path))
    raw = pd.read_excel(readable_path, sheet_name=0, header=0)

    resultados: list[PedidoNotaFiscal] = []
    for _, row in raw.iterrows():
        nf_raw = row.get("Nota Fiscal")
        if pd.isna(nf_raw):
            continue
        m = NF_PATTERN.match(str(nf_raw).strip())
        if not m:
            continue  # formato inesperado — não inventa, ignora a linha

        nf_num, serie, data_str = m.group(1), m.group(2), m.group(3)
        cliente_id, razao_social = _parse_cliente(row.get("Cliente"))
        representante_id, representante_nome = _parse_representante(row.get("Representante"))

        resultados.append(PedidoNotaFiscal(
            local=str(row.get("Local")).strip() if pd.notna(row.get("Local")) else "",
            pedido=str(row.get("Pedido")).strip() if pd.notna(row.get("Pedido")) else None,
            nota_fiscal=nf_num,
            serie=serie,
            data_emissao=parse_erp_date(data_str),
            cliente_id=cliente_id,
            razao_social=razao_social,
            representante_id=representante_id,
            representante_nome=representante_nome,
            raw_row=row.to_dict(),
        ))
    return resultados
