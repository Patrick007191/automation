#!/bin/bash
# Script para subir o código para o GitHub
# Execute NO GIT BASH (já está aberto)

echo "=== INICIANDO SUBIDA PARA O GITHUB ==="

# 1. Vai para a pasta do projeto
cd /c/Users/limma/Downloads/projeto_simara

# 2. Inicia o git
git init

# 3. Adiciona todos os arquivos
git add .

# 4. Cria o primeiro commit
git commit -m "App SIGED pronto para cloud"

echo ""
echo "=== PASSO 1 COMPLETO ==="
echo ""
echo "Agora va no navegador em https://github.com"
echo "Crie um repositório NOVO (botão verde 'New')"
echo "Nome: siged-automation"
echo "Deixe PUBLICO"
echo "DEPOIS volte aqui e execute os próximos comandos"