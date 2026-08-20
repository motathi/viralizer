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

python -m pip install -q -r requirements.txt
python -m src.painel.servidor

pause
