"""
Serviço de recuperação de documentos apagados.

Cenário real (relatado pelo cliente): o time de desenvolvimento do ERP
apagou documentos a receber a pedido do próprio cliente, e depois disso
esses títulos passaram a aparecer como 'TÍTULO DESCONTADO SEM
CORRESPONDÊNCIA' no motor (Regra 13) — o banco confirma que o título foi
liquidado via carteira de título descontado, mas não existe mais nenhum
registro correspondente no ERP.

Para recriar o documento, falta saber de qual Local ele deveria ter sido
lançado e para qual Cliente — informação que não está em nenhum dos
arquivos de conciliação, mas está no FTP050 (Relação de NF Emitidas),
cruzando pelo número da NF extraído do 'Seu Número' do banco.

Regra de extração: no Itaú, os últimos 2 dígitos do 'Seu Número' são a
Sequência da duplicata, e o restante é o número da Nota Fiscal — mesma
convenção usada em normalization.py para o Fatura/Seq do ERP (ex:
'3400622' -> NF 34006, Sequência 22).

Quando o número da NF aparece mais de uma vez no FTP050 (comum: Locais
diferentes reaproveitam a numeração), desempata pelo nome do cliente — o
primeiro nome do pagador do banco precisa aparecer na razão social do
FTP050. Sem isso, não escolhe nenhum candidato às cegas.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.bank_transaction import BankTransaction as BankTransactionRow
from app.models.nota_fiscal_emitida import NotaFiscalEmitida as NotaFiscalEmitidaRow
from app.models.reconciliation import Reconciliation
from app.models.reconciliation_match import ReconciliationMatchRow


@dataclass
class RecoveredTitle:
    match_id: UUID
    seu_numero: str
    nosso_numero: str
    nota_fiscal: str
    sequencia: str
    payer_name: str | None
    principal_amount: float | None
    due_date: date | None
    movement_date: date
    agency: str | None
    local_id: int | None
    local_nome: str | None
    cliente_id: str | None
    razao_social: str | None
    resolved: bool  # False = não achou nenhum candidato no FTP050


def _split_seu_numero(seu_numero: str) -> tuple[str, str]:
    """Últimos 2 dígitos = Sequência, resto = número da NF."""
    return seu_numero[:-2], seu_numero[-2:]


def find_recoverable_titles(session: Session, reconciliation_id: UUID) -> list[RecoveredTitle]:
    reconciliation = session.get(Reconciliation, reconciliation_id)
    if reconciliation is None:
        raise ValueError(f"Reconciliation {reconciliation_id} não encontrada.")

    matches = (
        session.query(ReconciliationMatchRow)
        .filter_by(reconciliation_id=reconciliation_id, status="TÍTULO DESCONTADO SEM CORRESPONDÊNCIA")
        .all()
    )

    # FTP050 não é importado por competência específica (pode cobrir anos)
    # — busca em todo o acervo já importado para esta conta.
    notas = (
        session.query(NotaFiscalEmitidaRow)
        .filter_by(bank_account_id=reconciliation.bank_account_id)
        .all()
    )
    notas_by_nf: dict[str, list[NotaFiscalEmitidaRow]] = {}
    for n in notas:
        notas_by_nf.setdefault(n.nota_fiscal, []).append(n)

    results: list[RecoveredTitle] = []
    for m in matches:
        bank: BankTransactionRow | None = m.bank_transaction
        if bank is None or not bank.seu_numero:
            continue

        nf_num, seq = _split_seu_numero(bank.seu_numero)
        candidatos = notas_by_nf.get(nf_num, [])

        escolhido: NotaFiscalEmitidaRow | None = None
        if len(candidatos) == 1:
            escolhido = candidatos[0]
        elif len(candidatos) > 1 and bank.payer_name:
            primeiro_nome = bank.payer_name.split()[0]
            correspondentes = [
                c for c in candidatos
                if c.razao_social and primeiro_nome.upper() in c.razao_social.upper()
            ]
            if len(correspondentes) >= 1:
                escolhido = correspondentes[0]

        results.append(RecoveredTitle(
            match_id=m.id,
            seu_numero=bank.seu_numero,
            nosso_numero=bank.nosso_numero,
            nota_fiscal=nf_num,
            sequencia=seq,
            payer_name=bank.payer_name,
            principal_amount=float(bank.principal_amount) if bank.principal_amount is not None else None,
            due_date=bank.due_date,
            movement_date=bank.movement_date,
            agency=bank.agency,
            local_id=escolhido.local_id if escolhido else None,
            local_nome=escolhido.local_nome if escolhido else None,
            cliente_id=escolhido.cliente_id if escolhido else None,
            razao_social=escolhido.razao_social if escolhido else None,
            resolved=escolhido is not None,
        ))

    return results
