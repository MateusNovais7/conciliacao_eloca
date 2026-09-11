"""
Autenticação — MVP.

Para o estágio atual (uso interno, poucos operadores), autenticação por
API key via header é suficiente e evita a complexidade de um sistema de
usuários completo antes de haver demanda real por múltiplos perfis de
acesso. Item 26 do escopo pede "autenticação" e "autorização" — isto
cobre autenticação; autorização por papel (ex: quem pode fechar
competência) fica registrada aqui como próximo passo quando houver mais
de um operador.

Não usar em produção multi-tenant sem evoluir para JWT + usuários — isto
é adequado para operação interna de um único time.
"""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.config import get_settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> str:
    settings = get_settings()
    if not settings.api_key:
        # Ambiente de desenvolvimento sem API_KEY configurada: não bloqueia,
        # mas isso nunca deve acontecer em produção (ver app.config.Settings,
        # que já valida isso quando APP_ENV=production).
        return "dev"
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key inválida ou ausente.")
    return x_api_key
