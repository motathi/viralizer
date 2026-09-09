"""O que a profissional escolheu — o único sinal que é sobre ELA.

O caderno aprende com o mercado: o que viraliza para os outros. Este
arquivo aprende com a pessoa: o que ela pôs na lista, o que gravou, o
que descartou com o X. A agenda local manda essas escolhas para o painel,
que as guarda aqui; a escrita recebe um resumo como preferência revelada
— sinal de gosto, não regra.
"""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ESTADOS = ("feita", "lista", "descartada")
MAX_DESCARTADAS_NO_PROMPT = 12


def _caminho(raiz: Path, nicho: str) -> Path:
    return raiz / "dados" / f"feedback-{nicho}.json"


def carregar(raiz: Path, nicho: str) -> dict:
    arquivo = _caminho(raiz, nicho)
    if not arquivo.exists():
        return {}
    try:
        return json.loads(arquivo.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def registrar(raiz: Path, nicho: str, semana: str, ideias: list[dict]) -> int:
    """Guarda o estado atual de cada ideia da semana (o último estado vale)."""
    dados = carregar(raiz, nicho)
    bloco = dados.setdefault(semana, {})
    agora = datetime.now().isoformat(timespec="minutes")
    for ideia in ideias:
        titulo = str(ideia.get("titulo", "")).strip()
        estado = str(ideia.get("estado", "")).strip()
        if not titulo:
            continue
        if estado in ESTADOS:
            bloco[titulo] = {"estado": estado, "pilar": ideia.get("pilar", ""),
                             "registro": ideia.get("registro", ""), "quando": agora}
        else:
            bloco.pop(titulo, None)  # voltou a "nenhum": esquece
    arquivo = _caminho(raiz, nicho)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return sum(len(b) for b in dados.values())


def preferencias(raiz: Path, nicho: str) -> dict | None:
    """Resumo compacto para o roteirista. None se ainda não há escolhas."""
    dados = carregar(raiz, nicho)
    escolhidas, descartadas = Counter(), Counter()
    vozes_sim, vozes_nao = Counter(), Counter()
    titulos_descartados = []
    total = 0
    for semana in sorted(dados):
        for titulo, info in dados[semana].items():
            total += 1
            pilar = (info.get("pilar") or "").split("(")[0].strip()
            voz = info.get("registro") or ""
            if info["estado"] in ("feita", "lista"):
                escolhidas[pilar] += 1
                if voz:
                    vozes_sim[voz] += 1
            else:
                descartadas[pilar] += 1
                if voz:
                    vozes_nao[voz] += 1
                titulos_descartados.append(titulo)
    if not total:
        return None
    return {
        "ideias_avaliadas": total,
        "pilares_que_ela_escolhe": dict(escolhidas.most_common(4)),
        "pilares_que_ela_descarta": dict(descartadas.most_common(4)),
        "vozes_que_ela_escolhe": dict(vozes_sim.most_common(4)),
        "vozes_que_ela_descarta": dict(vozes_nao.most_common(4)),
        "assuntos_descartados": titulos_descartados[-MAX_DESCARTADAS_NO_PROMPT:],
    }
