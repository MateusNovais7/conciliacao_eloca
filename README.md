# Conciliação Bancária — MEATHUNTER / Itaú

Sistema de conciliação bancária: motor de matching entre relatório ERP e extrato de
cobrança bancário, API FastAPI e frontend Next.js.

## Arquitetura

```
backend/
  app/
    api/              rotas FastAPI (clientes, contas, importações, conciliações, exports)
    importers/         parsers específicos por fonte (erp/ffp045a2.py, banks/itau_francesinha.py)
    reconciliation/     motor de matching (engine.py) + normalização + parsing
    models/             SQLAlchemy (Client, BankAccount, ImportFile, BankTransaction,
                         ERPTransaction, Reconciliation, ReconciliationMatchRow,
                         ManualAdjustment, AuditLog)
    services/           liga importadores/motor à persistência
    schemas/            Pydantic (request/response da API)
  database/migrations/  Alembic
  tests/                unitários, Golden Test, integração (API + banco)
frontend/
  app/                  Next.js App Router — nova conciliação, dashboard, investigação,
                         conciliação diária
docs/
  reconciliation-engine.md   documentação de cada regra do motor
```

Ver `docs/reconciliation-engine.md` para o detalhe de cada regra de conciliação e dos
achados reais de dados que viraram decisões de escopo.

## Instalação e desenvolvimento

### Backend
```bash
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env   # preencha DATABASE_URL, SECRET_KEY, API_KEY
export $(cat ../.env | xargs)
alembic upgrade head
uvicorn app.main:app --reload
```
Documentação interativa em `http://localhost:8000/docs`.

### Frontend
```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 NEXT_PUBLIC_API_KEY=<mesma API_KEY> npm run dev
```

## Testes
```bash
cd backend
PYTHONPATH=. pytest tests/ -v
```
Inclui: normalização/parsing, cada regra do motor isoladamente, o Golden Test
(roda contra os arquivos reais em `tests/fixtures/` e trava as contagens obtidas do
motor), integração de persistência, e o fluxo completo da API via `TestClient`.

## Migrations
```bash
cd backend
alembic revision --autogenerate -m "descrição da mudança"
alembic upgrade head
```
`DATABASE_URL` sempre vem de variável de ambiente — nunca hardcoded.

## Deploy (Docker / EasyPanel)
```bash
cp .env.example .env   # preencha as variáveis
docker compose build
docker compose up -d
```
**Atenção:** os Dockerfiles foram escritos com cuidado (healthcheck, usuário não-root,
migrations aplicadas no entrypoint do backend, build multi-stage no frontend), mas não
puderam ser testados neste ambiente por falta de um daemon Docker disponível. Rode
`docker compose build` e `docker compose up` num ambiente com Docker antes de promover
para produção/EasyPanel, e confira os healthchecks (`docker compose ps`) antes de
considerar o deploy validado.

Variáveis obrigatórias em produção (`APP_ENV=production`): `DATABASE_URL`,
`SECRET_KEY`, `API_KEY`, `CORS_ORIGINS`.

## Importadores existentes

- `app/importers/erp/ffp045a2.py` — relatório financeiro do ERP (repara automaticamente
  a stylesheet corrompida do arquivo original via LibreOffice headless).
- `app/importers/banks/itau_francesinha.py` — extrato de movimentação de cobrança Itaú.

### Como adicionar um novo banco
1. Crie `app/importers/banks/<banco>.py` retornando uma lista de `BankTransaction`
   (mesmo dataclass usado pelo Itaú — não crie um novo formato).
2. Documente no cabeçalho do arquivo a estrutura real observada no arquivo do banco
   (assim como foi feito para o Itaú) — nunca implemente sem ter visto o arquivo real.
3. O motor (`app/reconciliation/engine.py`) não precisa mudar: ele já trabalha em cima
   do formato normalizado.

### Como adicionar um novo relatório de ERP
Mesma lógica: novo arquivo em `app/importers/erp/`, retornando `ERPTransaction`.

## Regras do motor

Ver `docs/reconciliation-engine.md`. Resumo: Regras 1, 2, 3, 4, 5, 6, 7, 8 e 9
implementadas e testadas contra dados reais (98%+ de conciliação nos dados de
janeiro/2026); Regras 10/11 (agrupamento) deliberadamente não implementadas por falta
de evidência real nos dados disponíveis até agora.
