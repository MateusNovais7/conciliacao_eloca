from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database.deps import get_session
from app.database.session import Base
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_session():
        session = TestingSessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_fluxo_completo_ponta_a_ponta(client):
    # 1. health
    assert client.get("/health").json() == {"status": "ok"}

    # 2. cliente + conta
    r = client.post("/clientes", json={"name": "MEATHUNTER"})
    assert r.status_code == 201, r.text
    client_id = r.json()["id"]

    r = client.post("/contas", json={
        "client_id": client_id, "bank": "Itaú", "agency": "6157", "account_number": "98967-1",
    })
    assert r.status_code == 201, r.text
    account_id = r.json()["id"]

    # criar a mesma conta de novo (mesmo cliente/banco/número) deve ser
    # bloqueado — bug real encontrado em produção onde isso não acontecia
    r = client.post("/contas", json={
        "client_id": client_id, "bank": "Itaú", "agency": "6157", "account_number": "98967-1",
    })
    assert r.status_code == 409, r.text

    # 3. upload dos dois arquivos reais
    with open(FIXTURES / "erp_janeiro2026.xlsx", "rb") as f:
        r = client.post(
            "/importacoes/erp",
            data={"bank_account_id": account_id, "competencia_year": 2026,
                  "competencia_month": 1, "imported_by": "teste@meathunter.com"},
            files={"file": ("erp.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert r.status_code == 201, r.text
    erp_file_id = r.json()["id"]
    assert r.json()["row_count"] == 1858

    with open(FIXTURES / "itau_francesinha_janeiro2026.xlsx", "rb") as f:
        r = client.post(
            "/importacoes/banco",
            data={"bank_account_id": account_id, "competencia_year": 2026,
                  "competencia_month": 1, "imported_by": "teste@meathunter.com"},
            files={"file": ("banco.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert r.status_code == 201, r.text
    bank_file_id = r.json()["id"]

    # reimportar o mesmo arquivo é idempotente: reaproveita o import
    # existente (200, não 201) em vez de falhar — item 33 revisado após
    # uso real: como o hash garante conteúdo idêntico, não há razão para
    # bloquear o fluxo do usuário.
    with open(FIXTURES / "erp_janeiro2026.xlsx", "rb") as f:
        r = client.post(
            "/importacoes/erp",
            data={"bank_account_id": account_id, "competencia_year": 2026,
                  "competencia_month": 1, "imported_by": "outro@meathunter.com"},
            files={"file": ("erp-de-novo.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert r.status_code == 200
    assert r.json()["id"] == erp_file_id  # mesmo registro, não duplicou

    # 4. criar e executar conciliação
    r = client.post("/conciliacoes", json={
        "bank_account_id": account_id, "competencia_year": 2026, "competencia_month": 1,
        "erp_import_file_id": erp_file_id, "bank_import_file_id": bank_file_id,
    })
    assert r.status_code == 201, r.text
    reconciliation_id = r.json()["id"]

    r = client.post(f"/conciliacoes/{reconciliation_id}/executar")
    assert r.status_code == 200, r.text
    assert len(r.json()) == 1164

    # 4b. histórico da conta mostra essa competência com o percentual certo
    r = client.get("/conciliacoes", params={"bank_account_id": account_id})
    assert r.status_code == 200, r.text
    history = r.json()
    assert len(history) == 1
    assert history[0]["competencia_year"] == 2026
    assert history[0]["competencia_month"] == 1
    assert history[0]["reconciled_pct"] > 98.0

    # 5. dashboard fecha matematicamente
    r = client.get(f"/conciliacoes/{reconciliation_id}/dashboard")
    assert r.status_code == 200, r.text
    dash = r.json()
    assert sum(s["count"] for s in dash["by_status"]) == 1164
    assert dash["reconciled_pct"] > 98.0

    # 6. clicar num card = listar só aqueles títulos
    r = client.get(f"/conciliacoes/{reconciliation_id}/titulos", params={"status": "VALOR DIVERGENTE"})
    assert r.status_code == 200
    assert len(r.json()) == 6
    match_id = r.json()[0]["id"]

    # 7. busca global
    r = client.get(f"/conciliacoes/{reconciliation_id}/titulos", params={"search": "700521"})
    assert r.status_code == 200
    assert len(r.json()) >= 1

    # 8. detalhe do título
    r = client.get(f"/conciliacoes/{reconciliation_id}/titulos/{match_id}")
    assert r.status_code == 200
    assert r.json()["diagnostic"]

    # 9. ajuste manual (auditado)
    r = client.post(
        f"/conciliacoes/{reconciliation_id}/titulos/{match_id}/ajuste-manual",
        json={"reason": "AJUSTE_CONTABIL", "observation": "confirmado com o cliente",
              "new_status": "CONCILIADO MANUALMENTE", "performed_by": "financeiro@meathunter.com"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "CONCILIADO MANUALMENTE"
    assert r.json()["is_manual_override"] is True

    # 10. exportação Excel funciona
    r = client.get(f"/exports/{reconciliation_id}/excel")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert len(r.content) > 1000  # arquivo não vazio

    # 11. fechar competência
    r = client.post(f"/conciliacoes/{reconciliation_id}/fechar", params={"performed_by": "financeiro@meathunter.com"})
    assert r.status_code == 200
    assert r.json()["status"] == "FECHADA"

    # 12. não permite alteração silenciosa em competência fechada (item 20)
    r = client.post(f"/conciliacoes/{reconciliation_id}/executar")
    assert r.status_code == 409


def test_conciliacao_diaria(client):
    r = client.post("/clientes", json={"name": "MEATHUNTER"})
    client_id = r.json()["id"]
    r = client.post("/contas", json={
        "client_id": client_id, "bank": "Itaú", "agency": "6157", "account_number": "98967-1",
    })
    account_id = r.json()["id"]

    with open(FIXTURES / "erp_janeiro2026.xlsx", "rb") as f:
        r = client.post(
            "/importacoes/erp",
            data={"bank_account_id": account_id, "competencia_year": 2026,
                  "competencia_month": 1, "imported_by": "teste@meathunter.com"},
            files={"file": ("erp.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    erp_file_id = r.json()["id"]
    with open(FIXTURES / "itau_francesinha_janeiro2026.xlsx", "rb") as f:
        r = client.post(
            "/importacoes/banco",
            data={"bank_account_id": account_id, "competencia_year": 2026,
                  "competencia_month": 1, "imported_by": "teste@meathunter.com"},
            files={"file": ("banco.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    bank_file_id = r.json()["id"]

    r = client.post("/conciliacoes", json={
        "bank_account_id": account_id, "competencia_year": 2026, "competencia_month": 1,
        "erp_import_file_id": erp_file_id, "bank_import_file_id": bank_file_id,
    })
    reconciliation_id = r.json()["id"]
    client.post(f"/conciliacoes/{reconciliation_id}/executar")

    r = client.get(f"/conciliacoes/{reconciliation_id}/diaria")
    assert r.status_code == 200, r.text
    days = r.json()
    assert len(days) > 15  # ~21 dias úteis de janeiro

    # cada dia com diferença zero deve estar marcado OK; com diferença, DIVERGENTE
    for d in days:
        if abs(d["difference"]) < 0.01:
            assert d["status"] == "OK"
        else:
            assert d["status"] == "DIVERGENTE"

    # pelo menos um dia deve ter diferença (30/01, corte de fim de período)
    assert any(d["status"] == "DIVERGENTE" for d in days)
    # e o dia com diferença deve trazer os match_ids responsáveis (drill-down)
    divergent_day = next(d for d in days if d["status"] == "DIVERGENTE")
    assert len(divergent_day["match_ids"]) > 0


def test_excluir_conciliacao_duplicada_do_historico(client):
    r = client.post("/clientes", json={"name": "Cliente Exclusão"})
    client_id = r.json()["id"]
    r = client.post("/contas", json={
        "client_id": client_id, "bank": "Itaú", "agency": "6157", "account_number": "11111-1",
    })
    account_id = r.json()["id"]

    with open(FIXTURES / "erp_janeiro2026.xlsx", "rb") as f:
        r = client.post(
            "/importacoes/erp",
            data={"bank_account_id": account_id, "competencia_year": 2026,
                  "competencia_month": 1, "imported_by": "teste@empresa.com"},
            files={"file": ("erp.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    erp_file_id = r.json()["id"]
    with open(FIXTURES / "itau_francesinha_janeiro2026.xlsx", "rb") as f:
        r = client.post(
            "/importacoes/banco",
            data={"bank_account_id": account_id, "competencia_year": 2026,
                  "competencia_month": 1, "imported_by": "teste@empresa.com"},
            files={"file": ("banco.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    bank_file_id = r.json()["id"]

    # cria a mesma competência duas vezes (o cenário real relatado: usuário
    # importou repetido e ficou duplicado no histórico)
    ids = []
    for _ in range(2):
        r = client.post("/conciliacoes", json={
            "bank_account_id": account_id, "competencia_year": 2026, "competencia_month": 1,
            "erp_import_file_id": erp_file_id, "bank_import_file_id": bank_file_id,
        })
        ids.append(r.json()["id"])
        client.post(f"/conciliacoes/{r.json()['id']}/executar")

    r = client.get("/conciliacoes", params={"bank_account_id": account_id})
    assert len(r.json()) == 2

    # exclui a duplicata
    r = client.delete(f"/conciliacoes/{ids[0]}", params={"performed_by": "teste@empresa.com"})
    assert r.status_code == 204, r.text

    r = client.get("/conciliacoes", params={"bank_account_id": account_id})
    assert len(r.json()) == 1
    assert r.json()[0]["id"] == ids[1]

    # os arquivos importados continuam intactos (não é a exclusão que
    # apaga o dado original — item 6 do escopo)
    r = client.get("/importacoes", params={"bank_account_id": account_id})
    assert len(r.json()) == 2

    # competência fechada não pode ser excluída
    client.post(f"/conciliacoes/{ids[1]}/fechar", params={"performed_by": "teste@empresa.com"})
    r = client.delete(f"/conciliacoes/{ids[1]}", params={"performed_by": "teste@empresa.com"})
    assert r.status_code == 409


