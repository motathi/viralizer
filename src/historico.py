"""Memória das agendas já publicadas (anti-repetição entre semanas).

O pipeline registra tema e gancho de cada ideia publicada em
dados/historico-<nicho>.json e injeta esse histórico na etapa de pesquisa,
que fica proibida de repetir — ou apenas reformular — o que já saiu.
"""

import json
from datetime import date
from pathlib import Path

LIMITE_MEMORIA = 80  # itens enviados ao modelo (≈ 8 semanas de 10 ideias)


def _caminho(raiz: Path, nicho: str) -> Path:
    return raiz / "dados" / f"historico-{nicho}.json"


def carregar_historico(raiz: Path, nicho: str) -> list[dict]:
    """Temas/ganchos já publicados, do mais recente para o mais antigo."""
    arquivo = _caminho(raiz, nicho)
    if not arquivo.exists():
        return []
    itens = json.loads(arquivo.read_text(encoding="utf-8"))
    return itens[-LIMITE_MEMORIA:]


def registrar_historico(raiz: Path, nicho: str, roteiros: dict) -> int:
    """Acrescenta as ideias desta geração ao histórico. Retorna o total."""
    arquivo = _caminho(raiz, nicho)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    itens = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else []
    hoje = date.today().isoformat()
    for ideia in roteiros.get("ideias", []):
        ganchos = ideia.get("ganchos_3s") or [ideia.get("gancho_3s", "")]
        itens.append({
            "semana": hoje,
            "tema": ideia.get("titulo", ""),
            "gancho": next((g for g in ganchos if g), ""),
        })
    arquivo.write_text(json.dumps(itens, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(itens)
