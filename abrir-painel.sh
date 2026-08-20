#!/bin/bash
# Abre o painel (Linux)
cd "$(dirname "$0")" || exit 1

echo
echo "  Preparando o painel..."
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "  [ERRO] Python 3 nao encontrado. Instale com:"
  echo "    sudo apt install python3 python3-pip   # Debian/Ubuntu"
  exit 1
fi

python3 -m pip install -q -r requirements.txt
echo "  Preparando o navegador da coleta (so na primeira vez)..."
python3 -m playwright install chromium >/dev/null 2>&1
python3 -m src.painel.servidor
