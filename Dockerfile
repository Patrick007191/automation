# Dockerfile para deploy em cloud (Railway, Render, etc.)
# Base: Python oficial + Chromium para Playwright headless

FROM python:3.11-slim

# Instala dependências do sistema para Chromium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libgtk-3-0 \
    libasound2 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Define diretório de trabalho
WORKDIR /app

# Copia os arquivos do projeto
COPY . .

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Instala Chromium para Playwright
RUN python -m playwright install chromium && \
    python -m playwright install-deps chromium

# Expõe a porta (Railway usa $PORT, Render também)
EXPOSE 5000

# Comando de inicialização
CMD gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 600