@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Radar de Conteudo Viral

echo.
echo   Preparando o painel...
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo   [ERRO] Python nao encontrado.
  echo   Instale em https://www.python.org/downloads/ e marque
  echo   "Add Python to PATH" durante a instalacao.
  echo.
  pause
  exit /b 1
)

python -m pip install -q --disable-pip-version-check -r requirements.txt
echo   Preparando o navegador da coleta (so na primeira vez)...
python -m playwright install chromium >nul 2>&1
python -m src.painel.servidor

pause
