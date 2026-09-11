"""
Parsing utilitário para valores e datas nos formatos encontrados nos
arquivos reais (ERP FFP045A2 e extrato Itaú).
"""
from __future__ import annotations

from datetime import date, datetime


def parse_brl_currency(raw) -> float | None:
    """Converte string em formato brasileiro ('1.579,39') para float.

    Aceita já-numérico (alguns arquivos trazem a célula como número).
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip()
    if not text or text.lower() in {"nan", "none", "-"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    text = text.replace(".", "").replace(",", ".")
    try:
        value = float(text)
    except ValueError:
        return None
    return -value if negative else value


def parse_erp_date(raw) -> date | None:
    """Datas do ERP vêm como '01/01/2026 Qui' (dia + abreviação do dia da
    semana em português). A abreviação é só validação visual do relatório
    e é descartada aqui."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.lower() in {"nan", "none"}:
        return None
    day_part = text.split(" ")[0]
    try:
        return datetime.strptime(day_part, "%d/%m/%Y").date()
    except ValueError:
        return None


if __name__ == "__main__":
    assert parse_brl_currency("1.579,39") == 1579.39
    assert parse_brl_currency("504,46") == 504.46
    assert parse_brl_currency("-298.439,20") == -298439.20
    assert parse_brl_currency(None) is None
    assert parse_erp_date("05/01/2026 Seg") == date(2026, 1, 5)
    print("parsing.py: casos reais OK")
