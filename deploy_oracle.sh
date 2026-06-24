#!/bin/bash
# Script de instalação para Oracle Cloud Free Tier
# Execute como root ou sudo

echo "============================================"
echo "  Deploy Automacao SIGED - Oracle Cloud"
echo "============================================"

# 1. Atualiza sistema
apt update && apt upgrade -y

# 2. Instala dependencias
apt install -y python3 python3-pip python3-venv curl git

# 3. Instala Chrome para Playwright
curl -fsSL https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -o chrome.deb
apt install -y ./chrome.deb
rm chrome.deb

# 4. Instala dependencias do Chrome
apt install -y ca-certificates fonts-liberation libappindicator3-1 libasound2 libatk-bridge2.0-0 \
libatk1.0-0 libcups2 libdbus-1-3 libgdk-pixbuf2.0-0 libnspr4 libnss3 libx11-xcb1 libxcomposite1 \
libxdamage1 libxrandr2 xdg-utils libgbm1 libxkbcommon0

# 5. Clona o repositorio
cd /opt
git clone https://github.com/Patrick007191/automation.git automacao-siged
cd automacao-siged

# 6. Cria ambiente virtual
python3 -m venv venv
source venv/bin/activate

# 7. Instala dependencias Python
pip install flask playwright python-dotenv requests gunicorn

# 8. Instala Playwright Chromium
playwright install chromium
playwright install-deps chromium

# 9. Cria arquivo .env com as credenciais
cat > .env << 'EOF'
SITE_URL=https://protocolo.manaus.am.gov.br/proton/login.asp
SITE_LOGIN=951.698.652-87
SITE_SENHA=Shiajl89
EOF

# 10. Cria servico systemd para iniciar automaticamente
cat > /etc/systemd/system/automacao-siged.service << 'EOF'
[Unit]
Description=Automacao SIGED
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/automacao-siged
Environment="PATH=/opt/automacao-siged/venv/bin"
ExecStart=/opt/automacao-siged/venv/bin/gunicorn -w 1 -b 0.0.0.0:5000 app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 11. Inicia o servico
systemctl daemon-reload
systemctl enable automacao-siged
systemctl start automacao-siged

echo "============================================"
echo "  INSTALACAO CONCLUIDA!"
echo "============================================"
echo "  Acesse: http://SEU_IP_PUBLICO:5000"
echo "============================================"