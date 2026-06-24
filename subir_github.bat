@echo off
echo ============================================
echo   SUBINDO PARA GITHUB
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
    echo Depois execute este script novamente.
    pause
    exit /b 1
)

echo [1/5] Inicializando git...
git init

echo [2/5] Adicionando arquivos...
git add .

echo [3/5] Fazendo commit...
git commit -m "Projeto automacao SIGED para Render"

echo [4/5] Renomeando branch para main...
git branch -M main

echo [5/5] Conectando ao GitHub e enviando...
git remote add origin https://github.com/Patrick007191/automation_2.git
git push -u origin main

echo.
echo ============================================
echo   CONCLUIDO!
echo ============================================
echo.
echo Agora va em https://render.com e conecte o repositorio.
echo.
pause