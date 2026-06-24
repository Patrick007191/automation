@echo off
echo ============================================
echo   SUBINDO PARA GITHUB (automation)
echo ============================================
echo.

REM Verifica se git está instalado
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRO] Git nao encontrado!
    echo.
    echo Instale o Git em: https://git-scm.com/downloads
    echo Ou use o GitHub Desktop: https://desktop.github.com
    echo.
    pause
    exit /b 1
)

echo [1/6] Inicializando git...
git init

echo [2/6] Adicionando arquivos...
git add .

echo [3/6] Fazendo commit...
git commit -m "Atualizacao: navegador visivel + download manual"

echo [4/6] Renomeando branch para main...
git branch -M main

echo [5/6] Conectando ao repositorio existente...
git remote add origin https://github.com/Patrick007191/automation.git

echo [6/6] Enviando codigo (substituindo o antigo)...
git push -u origin main --force

echo.
echo ============================================
echo   CONCLUIDO!
echo ============================================
echo.
echo Agora va em https://render.com e conecte o repositorio.
echo.
pause