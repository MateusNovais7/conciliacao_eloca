from datetime import date

from app.reconciliation.parsing import parse_brl_currency, parse_erp_date


def test_parse_moeda_brl_milhares_e_decimais():
    assert parse_brl_currency("1.579,39") == 1579.39
    assert parse_brl_currency("504,46") == 504.46


def test_parse_moeda_brl_negativo():
    assert parse_brl_currency("-298.439,20") == -298439.20


def test_parse_moeda_brl_ja_numerico():
    assert parse_brl_currency(1579.39) == 1579.39


def test_parse_moeda_brl_vazio_ou_traco():
    assert parse_brl_currency(None) is None
    assert parse_brl_currency("-") is None


def test_parse_data_erp_com_dia_da_semana():
    assert parse_erp_date("05/01/2026 Seg") == date(2026, 1, 5)
    assert parse_erp_date("30/01/2026 Sex") == date(2026, 1, 30)


def test_parse_data_erp_invalida():
    assert parse_erp_date(None) is None
    assert parse_erp_date("não é data") is None
