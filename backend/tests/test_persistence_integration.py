from collections import Counter
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

import app.models  # noqa: F401 — registra os modelos
from app.database.session import Base, make_engine
from app.models.bank_account import BankAccount
from app.models.client import Client
from app.models.import_file import ImportFileKind
from app.models.reconciliation import Reconciliation
from app.services.import_service import DuplicateImportError, import_bank_file, import_erp_file
from app.services.reconciliation_service import run_and_persist_reconciliation

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def session():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def bank_account(session):
    client = Client(name="MEATHUNTER")
    session.add(client)
    session.flush()
    account = BankAccount(client_id=client.id, bank="Itaú", agency="6157", account_number="98967-1")
    session.add(account)
    session.flush()
    return account


def test_importacao_e_conciliacao_ponta_a_ponta_batem_com_golden_test(session, bank_account):
    erp_file = import_erp_file(
        session, bank_account.id, FIXTURES / "erp_janeiro2026.xlsx",
        competencia_year=2026, competencia_month=1,
        imported_by="teste@meathunter.com", storage_path="s3://fake/erp.xlsx",
    )
    bank_file = import_bank_file(
        session, bank_account.id, FIXTURES / "itau_francesinha_janeiro2026.xlsx",
        competencia_year=2026, competencia_month=1,
        imported_by="teste@meathunter.com", storage_path="s3://fake/banco.xlsx",
    )
    session.flush()

    assert erp_file.kind == ImportFileKind.ERP
    assert erp_file.row_count == 1858
    assert bank_file.row_count == 3047

    reconciliation = Reconciliation(
        bank_account_id=bank_account.id,
        competencia_year=2026, competencia_month=1,
        erp_import_file_id=erp_file.id, bank_import_file_id=bank_file.id,
    )
    session.add(reconciliation)
    session.flush()

    matches = run_and_persist_reconciliation(session, reconciliation.id)
    session.commit()

    assert len(matches) == 1164

    counts = Counter(m.status for m in matches)
    conciliados = sum(counts.get(s, 0) for s in (
        "CONCILIADO", "CONCILIADO D+1", "CONCILIADO D+2",
        "CORTE DE COMPETÊNCIA", "CORTE DE COMPETÊNCIA (fim do período importado)",
    ))
    assert conciliados == 1054  # mesmo número do Golden Test (tests/test_golden.py)

    # Confere que as linhas de match têm FK reais para bank/erp transactions
    # persistidas (não ficaram soltas sem referência).
    linked = [m for m in matches if m.bank_transaction_id or m.erp_transaction_id]
    assert len(linked) > 1000


def test_reimportar_mesmo_arquivo_e_bloqueado_por_hash(session, bank_account):
    import_erp_file(
        session, bank_account.id, FIXTURES / "erp_janeiro2026.xlsx",
        competencia_year=2026, competencia_month=1,
        imported_by="teste@meathunter.com", storage_path="s3://fake/erp.xlsx",
    )
    session.flush()

    with pytest.raises(DuplicateImportError):
        import_erp_file(
            session, bank_account.id, FIXTURES / "erp_janeiro2026.xlsx",
            competencia_year=2026, competencia_month=1,
            imported_by="outro-usuario@meathunter.com", storage_path="s3://fake/erp-de-novo.xlsx",
        )
