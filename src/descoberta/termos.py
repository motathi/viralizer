"""Histórico de desempenho de cada termo de busca, semana a semana.

Sem memória, o relatório de rendimento é impresso e esquecido: um termo que
falhou hoje pode ter sido ótimo nas três semanas anteriores, e nada
distingue os dois casos. Aqui cada coleta deixa registro, e é sobre esse
acumulado que o otimizador decide o que cortar.
"""

import json
from datetime import date
from pathlib import Path

LIMITE_RODADAS = 12  # ~3 meses de coletas semanais


def _caminho(raiz: Path, nicho: str) -> Path:
    return raiz / "dados" / f"termos-{nicho}.json"


def carregar(raiz: Path, nicho: str) -> list[dict]:
    arquivo = _caminho(raiz, nicho)
    if not arquivo.exists():
        return []
    try:
        return json.loads(arquivo.read_text(encoding="utf-8")).get("rodadas", [])
    except (ValueError, OSError):
        return []


def registrar(raiz: Path, nicho: str, coletados: dict[str, int],
              videos: list[dict], sugeridos: list[str]) -> int:
    """Guarda o resultado desta coleta. Devolve quantas rodadas há no total."""
    virais: dict[str, int] = {}
    for v in videos:
        termo = v.get("origem_termo")
        if termo:
            virais[termo] = virais.get(termo, 0) + 1

    termos = {t: {"coletados": coletados.get(t, 0), "virais": virais.get(t, 0)}
              for t in set(coletados) | set(virais)}
    rodadas = carregar(raiz, nicho)
    rodadas.append({"data": date.today().isoformat(), "termos": termos,
                    "sugeridos": sugeridos})
    rodadas = rodadas[-LIMITE_RODADAS:]

    arquivo = _caminho(raiz, nicho)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps({"rodadas": rodadas}, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    return len(rodadas)


def desempenho(rodadas: list[dict]) -> dict[str, dict]:
    """Consolida o histórico por termo: em quantas rodadas apareceu e o que rendeu."""
    resumo: dict[str, dict] = {}
    for rodada in rodadas:
        for termo, dados in rodada.get("termos", {}).items():
            r = resumo.setdefault(termo, {"rodadas": 0, "coletados": 0, "virais": 0,
                                          "rodadas_sem_viral": 0})
            r["rodadas"] += 1
            r["coletados"] += dados.get("coletados", 0)
            r["virais"] += dados.get("virais", 0)
            if not dados.get("virais"):
                r["rodadas_sem_viral"] += 1
    for r in resumo.values():
        r["virais_por_rodada"] = round(r["virais"] / r["rodadas"], 1) if r["rodadas"] else 0
    return resumo


def sugestoes_recorrentes(rodadas: list[dict], minimo: int = 2) -> list[str]:
    """Termos que a coleta sugeriu em pelo menos N rodadas — não foi acaso de uma."""
    contagem: dict[str, int] = {}
    for rodada in rodadas:
        for termo in rodada.get("sugeridos", []):
            contagem[termo] = contagem.get(termo, 0) + 1
    return [t for t, n in sorted(contagem.items(), key=lambda x: -x[1]) if n >= minimo]
