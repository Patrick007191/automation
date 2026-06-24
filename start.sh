#!/bin/bash
# Script de inicialização que instala Playwright e inicia o servidor

echo "=== INICIANDO SETUP DO PLAYWRIGHT ==="

# Instala o Chromium do Playwright
python -m playwright install chromium 2>&1 || true
python -m playwright install-deps chromium 2>&1 || true

echo "=== PLAYWRIGHT PRONTO ==="

# Inicia o servidor
exec gunicorn main:app --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 600