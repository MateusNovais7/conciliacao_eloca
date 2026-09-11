"""
Configuração central do banco de dados.

DATABASE_URL vem sempre de variável de ambiente — nunca hardcoded (item 26
do escopo). Exemplo para desenvolvimento local:
  DATABASE_URL=postgresql+psycopg2://user:senha@localhost:5432/conciliacao

Para rodar testes sem depender de um Postgres real, aceita também sqlite
(usado nos testes de integração desta suíte).
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL não configurada. Defina a variável de ambiente "
            "(ver .env.example) — nunca usamos credenciais hardcoded."
        )
    return url


def make_engine(url: str | None = None):
    return create_engine(url or get_database_url(), pool_pre_ping=True)


def make_session_factory(engine=None):
    return sessionmaker(bind=engine or make_engine(), expire_on_commit=False)
