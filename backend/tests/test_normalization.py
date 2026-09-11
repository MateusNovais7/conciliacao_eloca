from app.reconciliation.normalization import normalize_title


def test_normaliza_titulo_com_hifen_igual_a_sem_hifen():
    assert normalize_title("7005-21") == normalize_title("700521") == "700521"


def test_normaliza_preserva_zeros_a_esquerda():
    assert normalize_title("000521") == "000521"
    assert normalize_title("000521") != normalize_title("521")


def test_normaliza_remove_espacos_e_barras():
    assert normalize_title("  6710-23 ") == "671023"


def test_normaliza_none_retorna_none():
    assert normalize_title(None) is None
    assert normalize_title("") is None
    assert normalize_title("nan") is None
