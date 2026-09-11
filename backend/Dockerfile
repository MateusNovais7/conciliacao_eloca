FROM python:3.12-slim

# LibreOffice é necessário em runtime: o importador do ERP usa-o para
# reparar arquivos com stylesheet corrompida (ver app/importers/erp/ffp045a2.py).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-calc \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONPATH=/app


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x docker-entrypoint.sh

RUN useradd --create-home appuser \
    && mkdir -p /app/storage/uploads \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
