"""O arquivo de todas as agendas já geradas, num arquivo só.

A agenda deixou de ser "a semana atual + páginas separadas por semana": o
site mostra tudo numa lista só. Para isso é preciso guardar cada geração,
e não apenas a última — é o que este módulo faz.

`dados/agendas-<nicho>.json` acumula as gerações (a mais recente primeiro).
As semanas anteriores, que só existiam como HTML em web/semanas/, são
recuperadas na primeira execução: cada página arquivada carrega o JSON da
agenda embutido, então dá para semeá-las sem gerar nada de novo.
"""

import json
import re
from pathlib import Path

LIMITE_SEMANAS = 26  # meio ano de agendas; o resto sai da página


def _caminho(raiz: Path, nicho: str) -> Path:
    return raiz / "dados" / f"agendas-{nicho}.json"


def carregar(raiz: Path, nicho: str) -> list[dict]:
    """As gerações guardadas, da mais recente para a mais antiga."""
    arquivo = _caminho(raiz, nicho)
    if not arquivo.exists():
        return []
    try:
        agendas = json.loads(arquivo.read_text(encoding="utf-8")).get("agendas", [])
    except (ValueError, OSError):
        return []
    return sorted(agendas, key=lambda a: a.get("semana", ""), reverse=True)


def gravar(raiz: Path, nicho: str, agendas: list[dict]) -> Path:
    arquivo = _caminho(raiz, nicho)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    ordenadas = sorted(agendas, key=lambda a: a.get("semana", ""), reverse=True)
    arquivo.write_text(
        json.dumps({"agendas": ordenadas[:LIMITE_SEMANAS]}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return arquivo


def registrar(raiz: Path, nicho: str, semana: str, gerado_em: str,
              ideias: list[dict]) -> list[dict]:
    """Guarda (ou substitui) a geração de uma semana e devolve todas."""
    agendas = [a for a in carregar(raiz, nicho) if a.get("semana") != semana]
    agendas.append({"semana": semana, "gerado_em": gerado_em, "ideias": ideias})
    gravar(raiz, nicho, agendas)
    return carregar(raiz, nicho)


def semear_de_paginas(raiz: Path, nicho: str) -> int:
    """Recupera as semanas que só existem como HTML em web/semanas/.

    Roda uma vez: cada página arquivada tem o JSON da agenda embutido, e é
    dele que sai a lista de ideias. Devolve quantas semanas foram trazidas.
    """
    pasta = raiz / "web" / "semanas"
    if not pasta.exists():
        return 0
    agendas = carregar(raiz, nicho)
    conhecidas = {a.get("semana") for a in agendas}
    novas = 0
    for pagina in sorted(pasta.glob("*.html")):
        if pagina.stem in conhecidas:
            continue
        achado = re.search(
            r'<script id="dados-agenda" type="application/json">(.*?)</script>',
            pagina.read_text(encoding="utf-8"), re.S)
        if not achado:
            continue
        try:
            dados = json.loads(achado.group(1).replace("<\\/", "</"))
        except ValueError:
            continue
        ideias = dados.get("ideias") or []
        if not ideias:
            continue
        agendas.append({"semana": dados.get("semana") or pagina.stem,
                        "gerado_em": dados.get("gerado_em", ""), "ideias": ideias})
        novas += 1
    if novas:
        gravar(raiz, nicho, agendas)
    return novas
