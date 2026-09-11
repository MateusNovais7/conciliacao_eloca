from datetime import date

import pytest

from app.importers.banks.itau_francesinha import BankTransaction
from app.importers.erp.ffp045a2 import ERPTransaction
from app.reconciliation.engine import ReconciliationStatus, run_reconciliation
from app.reconciliation.normalization import normalize_title

BOLETO_DOC = "[5] - BOLETO BANCARIO"


def make_bank(seu_numero, valor, dia, op="liquidação", nosso=None, juros=0.0, tarifa=-1.0):
    return BankTransaction(
        bank="Itaú", account="98967", movement_date=dia,
        nosso_numero=nosso or f"N{seu_numero}",
        seu_numero=seu_numero, normalized_title=normalize_title(seu_numero),
        payer_name="CLIENTE TESTE", operation_type=op,
        principal_amount=valor, fee_amount=tarifa, interest_amount=juros,
        final_amount=valor + tarifa, source_sheet=dia.strftime("%d-%m-%Y"),
    )


def make_erp(titulo, valor, dia, tipo="Rec. Dup.", doc=BOLETO_DOC, antecipacao=False):
    return ERPTransaction(
        account_local="MEAT HUNTER", transaction_date=dia,
        invoice_number_raw=titulo, normalized_title=normalize_title(titulo),
        tipo=tipo, tipo_documento=doc, nota_fiscal=None,
        descricao="ANTECIPAÇÃO RECEBIVEIS" if antecipacao else "",
        incoming_amount=valor, outgoing_amount=None, balance=0.0,
        is_anticipation=antecipacao,
    )


def status_for(results, seu_numero=None, titulo=None):
    for r in results:
        if seu_numero and r.bank_tx and r.bank_tx.seu_numero == seu_numero:
            return r.status
        if titulo and r.erp_tx and r.erp_tx.invoice_number_raw == titulo:
            return r.status
    return None


class TestRegra1MatchExato:
    def test_titulo_valor_e_data_iguais_concilia(self):
        bank = [make_bank("1001", 1000.00, date(2026, 1, 6))]  # terça
        erp = [make_erp("1001", 1000.00, date(2026, 1, 6))]
        results = run_reconciliation(bank, erp)
        assert status_for(results, seu_numero="1001") == ReconciliationStatus.CONCILIADO


class TestRegra2DPlus:
    def test_d_mais_1_dia_util_puro_terca_para_quarta(self):
        bank = [make_bank("1002", 500.00, date(2026, 1, 6))]   # terça
        erp = [make_erp("1002", 500.00, date(2026, 1, 7))]     # quarta
        results = run_reconciliation(bank, erp)
        assert status_for(results, seu_numero="1002") == ReconciliationStatus.CONCILIADO_D1

    def test_d_mais_2_dias_uteis(self):
        bank = [make_bank("1003", 700.00, date(2026, 1, 6))]   # terça
        erp = [make_erp("1003", 700.00, date(2026, 1, 8))]     # quinta
        results = run_reconciliation(bank, erp)
        assert status_for(results, seu_numero="1003") == ReconciliationStatus.CONCILIADO_D2

    def test_sexta_para_segunda_e_corte_de_competencia_por_fim_de_semana(self):
        bank = [make_bank("1004", 900.00, date(2026, 1, 2))]   # sexta
        erp = [make_erp("1004", 900.00, date(2026, 1, 5))]     # segunda
        results = run_reconciliation(bank, erp)
        assert status_for(results, seu_numero="1004") == ReconciliationStatus.CORTE_COMPETENCIA


class TestRegra3Juros:
    def test_valor_cliente_soma_principal_e_juros_sem_descontar_tarifa(self):
        bank = make_bank("1005", 735.73, date(2026, 1, 6), juros=55.17, tarifa=-1.0)
        assert bank.client_amount == pytest.approx(790.90)


class TestRegra4ValorDivergente:
    def test_mesmo_titulo_valor_diferente_nao_forca_conciliacao(self):
        bank = [make_bank("1006", 1000.00, date(2026, 1, 6))]
        erp = [make_erp("1006", 850.00, date(2026, 1, 6))]
        results = run_reconciliation(bank, erp)
        assert status_for(results, seu_numero="1006") == ReconciliationStatus.VALOR_DIVERGENTE


class TestRegra6Antecipacao:
    def test_titulo_antecipacao_nao_entra_no_matching_normal(self):
        bank = [make_bank("1007", 300.00, date(2026, 1, 6))]
        erp = [make_erp("1007", 300.00, date(2026, 1, 6), antecipacao=True)]
        results = run_reconciliation(bank, erp)
        # Sem correspondência de antecipação no ERP, o título do banco fica
        # sem par (não deve aparecer como CONCILIADO).
        assert status_for(results, seu_numero="1007") == ReconciliationStatus.BANCO_SEM_ERP


class TestRegra7e8SemCorrespondencia:
    def test_banco_sem_erp(self):
        bank = [make_bank("1008", 400.00, date(2026, 1, 6))]
        results = run_reconciliation(bank, [])
        assert status_for(results, seu_numero="1008") == ReconciliationStatus.BANCO_SEM_ERP

    def test_erp_sem_banco(self):
        erp = [make_erp("1009", 400.00, date(2026, 1, 6))]
        results = run_reconciliation([], erp)
        assert status_for(results, titulo="1009") == ReconciliationStatus.ERP_SEM_BANCO


class TestEscopoTituloDescontadoEForaDeCarteira:
    def test_titulo_descontado_nao_e_comparado_como_divergencia(self):
        bank = [make_bank("1010", 5000.00, date(2026, 1, 6), op="liquidação de título descontado")]
        results = run_reconciliation(bank, [])
        assert status_for(results, seu_numero="1010") == ReconciliationStatus.TITULO_DESCONTADO

    def test_pix_do_erp_fora_do_escopo_da_francesinha_nao_vira_erp_sem_banco(self):
        erp = [make_erp("1011", 200.00, date(2026, 1, 6), doc="[2] - PIX")]
        results = run_reconciliation([], erp)
        # PIX não é coberto por este importador bancário — não deve gerar
        # nenhum resultado (nem falso ERP_SEM_BANCO).
        assert all(r.erp_tx is None or r.erp_tx.invoice_number_raw != "1011" for r in results)


class TestRegra33Idempotencia:
    def test_mesmo_titulo_nao_e_usado_duas_vezes_no_matching(self):
        # Duas liquidações com o mesmo Seu Número (parcelas diferentes já
        # deveriam ter normalized_title distinto na prática, mas o motor
        # não pode casar duas vezes o mesmo registro ERP).
        bank = [
            make_bank("1012", 100.00, date(2026, 1, 6), nosso="A"),
            make_bank("1012", 100.00, date(2026, 1, 6), nosso="B"),
        ]
        erp = [make_erp("1012", 100.00, date(2026, 1, 6))]
        results = run_reconciliation(bank, erp)
        conciliados = [r for r in results if r.status == ReconciliationStatus.CONCILIADO]
        assert len(conciliados) == 1


class TestRegra9PossivelCorrespondencia:
    def test_titulo_diferente_valor_e_data_proximos_e_nome_parecido_vira_possivel(self):
        # Título completamente diferente no banco e no ERP, mas valor quase
        # igual, data próxima e nome do pagador/cliente batendo — não pode
        # ser conciliado automaticamente, mas deve virar candidato.
        bank = [make_bank("9999", 1000.00, date(2026, 1, 6))]
        bank[0].payer_name = "RESTAURANTE BOM SABOR LTDA"
        erp = [make_erp("8888", 1000.02, date(2026, 1, 7))]
        erp[0].descricao = "8888 Tipo Baixa: PGTO EM BOLETO Cliente: RESTAURANTE BOM SABOR LTDA -  ( Danfe: 8888 )"
        results = run_reconciliation(bank, erp)
        assert status_for(results, seu_numero="9999") == ReconciliationStatus.POSSIVEL_CORRESPONDENCIA

    def test_sem_candidato_proximo_continua_banco_sem_erp(self):
        bank = [make_bank("7777", 1000.00, date(2026, 1, 6))]
        erp = [make_erp("6666", 50.00, date(2026, 6, 1))]  # valor e data muito distantes
        results = run_reconciliation(bank, erp)
        assert status_for(results, seu_numero="7777") == ReconciliationStatus.BANCO_SEM_ERP

