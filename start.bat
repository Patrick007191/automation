@echo off
chcp 65001 >nul
title Automacao SIGED - Download de Processos
cd /d "%~dp0"

echo ============================================================
echo    AUTOMACAO SIGED - Download de Processos
echo    Modo Portatil (levar no pendrive)
echo ============================================================
echo.
echo  Pasta atual: %~dp0
echo.

REM ============================================================
REM PASSO 1: Instalar Python se necessario
REM ============================================================
:VERIFICAR_PYTHON
echo [1/5] Verificando Python...
python --version >nul 2>&1
if not errorlevel 1 goto PYTHON_OK

echo.
echo  [AVISO] Python nao encontrado!
echo  Baixando e instalando Python automaticamente...
echo.
echo  Baixando Python 3.12.3...
powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe' -OutFile '%temp%\python-installer.exe'" 2>nul
if errorlevel 1 (
    bitsadmin /transfer "DownloadPython" https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe "%temp%\python-installer.exe" >nul 2>&1
)
if not exist "%temp%\python-installer.exe" (
    echo [ERRO] Nao foi possivel baixar Python!
    echo Baixe de: https://python.org/downloads/
    pause
    exit /b 1
)
echo Instalando Python...
start /wait "" "%temp%\python-installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
echo [OK] Python instalado!
ping 127.0.0.1 -n 3 >nul
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao detectado.
    pause
    exit /b 1
)
:PYTHON_OK
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VER=%%i
echo [OK] Python %PYTHON_VER% encontrado!
echo.

REM ============================================================
REM PASSO 2: Instalar dependencias
REM ============================================================
echo [2/5] Instalando dependencias...
python -m pip install --upgrade pip --quiet 2>nul
pip install -r requirements.txt --quiet --upgrade
if errorlevel 1 (
    pip install -r requirements.txt
)
echo [OK] Dependencias instaladas!
echo.

REM ============================================================
REM PASSO 3: Instalar Playwright se necessario
REM ============================================================
echo [3/5] Verificando Playwright...
python verificar_playwright.py
if errorlevel 1 goto INSTALAR_PLAYWRIGHT
echo [OK] Playwright pronto!
goto FIM_PLAYWRIGHT

:INSTALAR_PLAYWRIGHT
echo Instalando Chromium (primeira vez - ~150MB)...
python -m playwright install chromium
if errorlevel 1 (
    echo [ERRO] Falha ao instalar Chromium.
    pause
    exit /b 1
)
echo [OK] Chromium instalado!

:FIM_PLAYWRIGHT
echo.

REM ============================================================
REM PASSO 4: Verificar .env
REM ============================================================
echo [4/5] Verificando configuracao...
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo Criado arquivo .env de exemplo.
    echo.
    echo Abrindo .env para configuracao...
    start notepad.exe ".env"
    echo.
    echo Preencha seu CPF e senha, salve e feche.
    echo Pressione ENTER apos configurar.
    pause
)
findstr /C:"seu_cpf_aqui" ".env" >nul 2>&1
if not errorlevel 1 (
    echo.
    echo Configure suas credenciais no .env primeiro!
    start notepad.exe ".env"
    pause
    exit /b 1
)
echo [OK] Configuracao encontrada!
echo.

REM ============================================================
REM PASSO 5: Iniciar servidor
REM ============================================================
echo [5/5] Iniciando servidor...
echo.
echo ============================================================
echo    SERVICOR INICIADO!
echo.
echo    Acesse: http://127.0.0.1:5000
echo.
echo    PDFs salvos em: %~dp0downloads\
echo.
echo    NAO FECHE ESTA JANELA!
echo    Pressione Ctrl+C para parar.
echo ============================================================
echo.

start http://127.0.0.1:5000
python app.py

echo.
echo  Servidor encerrado.
pause