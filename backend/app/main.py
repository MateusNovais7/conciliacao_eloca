from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import clientes, conciliacoes, contas, exports, importacoes
from app.config import get_settings

logger = logging.getLogger("conciliacao")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Conciliação Bancária — MEATHUNTER",
    description="Motor de conciliação bancária: ERP × extrato de cobrança.",
    version="0.1.0",
)

settings = get_settings()
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Item 34: erros técnicos vão para o log, nunca para a resposta.
    logger.exception("Erro não tratado em %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={"detail": "Ocorreu um erro inesperado. A equipe técnica já foi notificada."},
    )


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(clientes.router)
app.include_router(contas.router)
app.include_router(importacoes.router)
app.include_router(conciliacoes.router)
app.include_router(exports.router)
