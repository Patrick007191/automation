@echo off
chcp 65001 >nul
title Apresentacao SIGED
cd /d "%~dp0"

echo ============================================================
echo    AUTOMACAO SIGED - Apresentacao do Projeto
echo ============================================================
echo.
echo  Abrindo apresentacao no navegador...

REM Cria um script VBS temporario que abre o HTML no navegador padrao
REM (Isso e mais confiavel que "start" porque o VBScript usa a API do Windows)
echo Set shell = CreateObject("WScript.Shell") > "%temp%\abrir_siged.vbs"
echo shell.Run "rundll32.exe url.dll,FileProtocolHandler " ^& chr(34) ^& "%~dp0demo.html" ^& chr(34), 1, False >> "%temp%\abrir_siged.vbs"
echo Set shell = Nothing >> "%temp%\abrir_siged.vbs"

REM Executa o VBScript
cscript //nologo "%temp%\abrir_siged.vbs"

REM Remove o temporario
del "%temp%\abrir_siged.vbs" 2>nul

echo  ✅ Apresentacao aberta no navegador!
echo.
echo  Se nao abrir, faca:
echo  1. Va ate a pasta do projeto
echo  2. De 2 cliques em "apresentar.vbs"
echo  3. Ou abra "demo.html" manualmente
echo.
timeout /t 5 >nul
exit