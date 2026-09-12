"""
Serviço de recuperação de documentos apagados.

Cenário real (relatado pelo cliente): o time de desenvolvimento do ERP
apagou documentos a receber a pedido do próprio cliente, e depois disso
esses títulos passaram a aparecer como 'TÍTULO DESCONTADO SEM
CORRESPONDÊNCIA' no motor (Regra 13) — o banco confirma que o título foi
liquidado via carteira de título descontado, mas não existe mais nenhum
registro correspondente no ERP.

Para recriar o documento, falta saber de qual Local, para qual Cliente e
com qual Representante ele deveria ter sido lançado — informação que não
está em nenhum dos arquivos de conciliação. Duas fontes complementares:

  FTP050    (Relação de NF Emitidas) -> Local, Cliente, Data de Emissão
  FTP021A1  (Pedidos/Notas Fiscais)  -> Representante (e também
                                         Local/Cliente/Data, usados como
                                         desempate secundário)

Cruzamento pelo número da NF extraído do 'Seu Número' do banco: no Itaú,
os últimos 2 dígitos são a Sequência da duplicata, e o restante é o
número da Nota Fiscal (ex: '3400622' -> NF 34006, Sequência 22).

Quando o número da NF aparece mais de uma vez numa fonte, desempata pelo
nome do cliente — o primeiro nome do pagador do banco precisa aparecer na
razão social daquela fonte. Sem isso, não escolhe nenhum candidato às
cegas (nem Local/Cliente, nem Representante, separadamente).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.bank_transaction import BankTransaction as BankTransactionRow
from app.models.nota_fiscal_emitida import NotaFiscalEmitida as NotaFiscalEmitidaRow
from app.models.pedido_nota_fiscal import PedidoNotaFiscal as PedidoNotaFiscalRow
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
    data_emissao: date | None
    representante_id: str | None
    representante_nome: str | None
    resolved: bool  # False = não achou Local/Cliente em nenhuma fonte


def _split_seu_numero(seu_numero: str) -> tuple[str, str]:
    """Últimos 2 dígitos = Sequência, resto = número da NF."""
    return seu_numero[:-2], seu_numero[-2:]


def _escolher_por_nome(candidatos: list, payer_name: str | None, razao_attr: str = "razao_social"):
    """Desempate genérico: exige match do primeiro nome do pagador contra
    a razão social do candidato. Nunca escolhe às cegas se houver mais de
    um candidato e nenhum bater o nome."""
    if len(candidatos) == 1:
        return candidatos[0]
    if len(candidatos) > 1 and payer_name:
        primeiro_nome = payer_name.split()[0]
        correspondentes = [
            c for c in candidatos
            if getattr(c, razao_attr, None) and primeiro_nome.upper() in getattr(c, razao_attr).upper()
        ]
        if len(correspondentes) >= 1:
            return correspondentes[0]
    return None


def find_recoverable_titles(session: Session, reconciliation_id: UUID) -> list[RecoveredTitle]:
    reconciliation = session.get(Reconciliation, reconciliation_id)
    if reconciliation is None:
        raise ValueError(f"Reconciliation {reconciliation_id} não encontrada.")

    matches = (
        session.query(ReconciliationMatchRow)
        .filter_by(reconciliation_id=reconciliation_id, status="TÍTULO DESCONTADO SEM CORRESPONDÊNCIA")
        .all()
    )

    # Nem FTP050 nem FTP021A1 são importados por competência específica
    # (podem cobrir anos) — busca em todo o acervo já importado pra conta.
    notas = (
        session.query(NotaFiscalEmitidaRow)
        .filter_by(bank_account_id=reconciliation.bank_account_id)
        .all()
    )
    notas_by_nf: dict[str, list[NotaFiscalEmitidaRow]] = {}
    for n in notas:
        notas_by_nf.setdefault(n.nota_fiscal, []).append(n)

    pedidos = (
        session.query(PedidoNotaFiscalRow)
        .filter_by(bank_account_id=reconciliation.bank_account_id)
        .all()
    )
    pedidos_by_nf: dict[str, list[PedidoNotaFiscalRow]] = {}
    for p in pedidos:
        pedidos_by_nf.setdefault(p.nota_fiscal, []).append(p)

    results: list[RecoveredTitle] = []
    for m in matches:
        bank: BankTransactionRow | None = m.bank_transaction
        if bank is None or not bank.seu_numero:
            continue

        nf_num, seq = _split_seu_numero(bank.seu_numero)

        nota = _escolher_por_nome(notas_by_nf.get(nf_num, []), bank.payer_name)
        pedido = _escolher_por_nome(pedidos_by_nf.get(nf_num, []), bank.payer_name)

        # Local/Cliente: prioriza o FTP050 (fonte original pensada pra
        # isso); usa o FTP021A1 como alternativa se o FTP050 não resolveu.
        local_id = nota.local_id if nota else None
        local_nome = nota.local_nome if nota else (pedido.local if pedido else None)
        cliente_id = nota.cliente_id if nota else (pedido.cliente_id if pedido else None)
        razao_social = nota.razao_social if nota else (pedido.razao_social if pedido else None)
        data_emissao = nota.data_emissao if nota else (pedido.data_emissao if pedido else None)

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
            local_id=local_id,
            local_nome=local_nome,
            cliente_id=cliente_id,
            razao_social=razao_social,
            data_emissao=data_emissao,
            representante_id=pedido.representante_id if pedido else None,
            representante_nome=pedido.representante_nome if pedido else None,
            resolved=bool(cliente_id and local_id is not None),
        ))

    return results
