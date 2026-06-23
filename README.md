# Automação SIGED - Download de Processos

Sistema web para baixar automaticamente documentos de processos do SIGED.
Acessível de qualquer máquina via navegador.

## 🚀 Deploy no Railway.app (gratuito e recomendado)

### 1. Crie uma conta no Railway.app
- Acesse https://railway.app e crie uma conta (GitHub)
- Railway oferece $5 de crédito grátis/mês (mais que suficiente)

### 2. Prepare o repositório no GitHub

Primeiro, **remova o arquivo `.env` do staging** (para não subir credenciais):

```bash
# Remove .env do tracking (sem deletar o arquivo)
git rm --cached .env
```

Depois faça o commit:

```bash
git init
git add .
git commit -m "App SIGED com suporte a deploy cloud"
```

Crie um repositório **público** no GitHub e envie:

```bash
git remote add origin https://github.com/SEU_USUARIO/siged-automation.git
git branch -M main
git push -u origin main
```

### 3. Deploy no Railway

1. No Railway.app, clique **New Project** → **Deploy from GitHub repo**
2. Selecione seu repositório
3. Railway detecta automaticamente o `nixpacks.toml` e faz o build
4. **IMPORTANTE**: Adicione as variáveis de ambiente (secrets) em:
   - Railway Dashboard → seu projeto → **Variables**
   - Adicione:

| Variável | Valor | Descrição |
|----------|-------|-----------|
| `SITE_LOGIN` | `951.698.652-87` | Seu CPF de acesso ao SIGED |
| `SITE_SENHA` | `sua_senha` | Sua senha do SIGED |
| `SITE_URL` | `https://protocolo.manaus.am.gov.br/proton/login.asp` | URL do portal |
| `HEADLESS` | `true` | Força modo headless |

5. Railway vai fazer o build e disponibilizar uma URL pública como:
   `https://siged-automation.up.railway.app`

## 🖥️ Uso Local (alternativa)

```bash
# Instalar dependências
pip install -r requirements.txt
python -m playwright install chromium

# Configurar credenciais
cp .env.example .env
# Edite .env com seu CPF e senha

# Rodar
python app.py
```

Acesse: http://127.0.0.1:5000

## 🔒 Segurança

- **NUNCA** commit o arquivo `.env` - o `.gitignore` já bloqueia
- As credenciais ficam armazenadas com segurança nas **Variables** do Railway (criptografadas)
- O repositório no GitHub fica público mas **sem nenhuma senha exposta**

## 📦 Estrutura

```
projeto_simara/
├── app.py              # Servidor Flask + automação Playwright
├── auto_download.py    # Download de PDF via Playwright (nativo)
├── templates/
│   └── index.html      # Interface web
├── .gitignore          # Arquivos ignorados
├── requirements.txt    # Dependências Python
├── setup.sh            # Script de setup
├── nixpacks.toml       # Config Railway
└── README.md           # Este arquivo