"""
Normalização de identificadores de título.

Caso real observado (arquivos MEATHUNTER / Itaú 98967-1, janeiro/2026):
  Banco (Seu Número): 700521
  ERP  (Fatura/Seq):  7005-21
Ambos devem normalizar para o mesmo valor.

Regra: remover apenas caracteres de formatação que não alteram o significado
do identificador (hífen, ponto, espaço, barra). NUNCA fazer int(valor), pois
isso descartaria zeros à esquerda relevantes (ex: "000521" != "521").
"""
import re

_FORMATTING_CHARS = re.compile(r"[-.\s/]")


def normalize_title(raw: str | None) -> str | None:
    """Normaliza um identificador de título para comparação entre ERP e banco.

    Mantém todos os dígitos e letras na ordem original; remove apenas
    separadores de formatação. Preserva zeros à esquerda.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.lower() in {"nan", "none"}:
        return None
    normalized = _FORMATTING_CHARS.sub("", text)
    return normalized.upper() or None


if __name__ == "__main__":
    # Casos reais confirmados nos arquivos de janeiro/2026
    assert normalize_title("7005-21") == normalize_title("700521") == "700521"
    assert normalize_title("6710-23") == "671023"
    assert normalize_title("  681721 ") == "681721"
    assert normalize_title(None) is None
    print("normalization.py: casos reais OK")
