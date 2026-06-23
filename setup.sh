#!/usr/bin/env bash
# Script de setup para deploy em cloud (Railway.app, Render, Heroku)
# Instala as dependências do Playwright (Chromium) para modo headless

set -e

echo "=== INICIANDO SETUP ==="

# Instala as dependências Python
pip install -r requirements.txt

# Instala os navegadores do Playwright (apenas Chromium para economizar espaço)
python -m playwright install chromium

# Instala as dependências de sistema necessárias para o Chromium rodar headless
python -m playwright install-deps chromium

echo "=== SETUP CONCLUÍDO ==="