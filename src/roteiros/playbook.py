"""Caderno de aprendizado do nicho: o que as pesquisas já descobriram.

Toda semana a etapa de pesquisa decifra padrões, vozes e aberturas dos
virais. Sem memória, isso evapora e a próxima semana recomeça do zero.
Aqui cada descoberta é depositada e consolidada:

- o que se repete em várias semanas vira conhecimento CONSOLIDADO;
- o que apareceu uma vez fica EM OBSERVAÇÃO (pode ser modinha);
- o que some por muitas semanas é aposentado (DORMENTE) — sai dos
  prompts, mas não é apagado.

O caderno é injetado nas duas etapas: a pesquisa usa para distinguir o
estrutural do passageiro; a escrita recebe a versão destilada (o manual,
em src/roteiros/manual.py).
"""

import json
import re
from datetime import date
from pathlib import Path

from src.texto import parecidos, tokens

SEMANAS_ATE_DORMIR = 8   # sem aparecer por tanto tempo, sai dos prompts
MAX_POR_LISTA = 40       # teto de entradas vivas por categoria
MAX_EVIDENCIAS = 4       # exemplos guardados por entrada
LIMITE_FUSAO = 0.4       # jaccard acima disso = mesma entrada
RADICAL = 5              # "desmontado"/"desmontar" -> "desmo"


def _caminho(raiz: Path, nicho: str) -> Path:
    return raiz / "dados" / f"playbook-{nicho}.json"


def vazio() -> dict:
    return {"semanas": [], "padroes": [], "vozes": [], "aberturas": [],
            "vocabulario": {}}


def carregar(raiz: Path, nicho: str) -> dict:
    arquivo = _caminho(raiz, nicho)
    if not arquivo.exists():
        return vazio()
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return vazio()
    base = vazio()
    base.update(dados)
    return base


def salvar(raiz: Path, nicho: str, playbook: dict) -> Path:
    arquivo = _caminho(raiz, nicho)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(playbook, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    return arquivo


def _prefixo(texto: str, palavras: int = 2) -> str:
    """As primeiras palavras, sem pontuação: a "jogada" de uma abertura."""
    limpas = [p for p in re.findall(r"[a-zà-ú]+", texto.lower())]
    return " ".join(limpas[:palavras])


def _mesma_entrada(a: str, b: str, modo: str) -> bool:
    if modo == "prefixo":
        # aberturas são curtas ("Para de...", "Ninguém te falou"): o que
        # importa é a jogada inicial, não o resto da frase
        pa, pb = _prefixo(a), _prefixo(b)
        return bool(pa) and pa == pb
    return parecidos(tokens(a, RADICAL), tokens(b, RADICAL), LIMITE_FUSAO)


def _depositar(lista: list[dict], texto: str, semana: str,
               evidencia: str = "", metrica: str = "", modo: str = "assunto") -> None:
    """Funde com uma entrada parecida ou cria uma nova."""
    texto = (texto or "").strip()
    if not texto:
        return
    for entrada in lista:
        if _mesma_entrada(texto, entrada["texto"], modo):
            if semana not in entrada["semanas"]:
                entrada["semanas"].append(semana)
            if evidencia and evidencia not in entrada["evidencias"]:
                entrada["evidencias"] = (entrada["evidencias"] + [evidencia])[-MAX_EVIDENCIAS:]
            if metrica:
                entrada["metricas"] = (entrada.get("metricas", []) + [metrica])[-MAX_EVIDENCIAS:]
            return
    lista.append({"texto": texto, "semanas": [semana],
                  "evidencias": [evidencia] if evidencia else [],
                  "metricas": [metrica] if metrica else []})


def absorver(playbook: dict, briefing: dict, semana: str | None = None) -> dict:
    """Deposita no caderno o que a pesquisa desta semana descobriu."""
    semana = semana or date.today().isoformat()
    if semana not in playbook["semanas"]:
        playbook["semanas"].append(semana)

    for p in briefing.get("padroes_da_semana", []):
        _depositar(playbook["padroes"], p.get("padrao", ""), semana, p.get("evidencia", ""))
    for v in briefing.get("vozes_da_semana", []):
        _depositar(playbook["vozes"], v.get("registro", ""), semana, v.get("evidencia", ""))

    for pauta in briefing.get("pautas", []):
        # a métrica do melhor viral de origem acompanha o padrão aplicado
        metrica = ""
        for viral in pauta.get("virais_origem", []):
            if viral.get("metrica"):
                metrica = viral["metrica"]
                break
        if pauta.get("padrao_aplicado"):
            _depositar(playbook["padroes"], pauta["padrao_aplicado"], semana, metrica=metrica)

        ling = pauta.get("linguagem") or {}
        exemplos = ling.get("trechos_literais") or []
        exemplo = exemplos[0] if exemplos else ""
        _depositar(playbook["vozes"], ling.get("registro", ""), semana, exemplo)
        _depositar(playbook["aberturas"], ling.get("abertura", ""), semana, exemplo,
                   metrica, modo="prefixo")
        for palavra in ling.get("vocabulario") or []:
            chave = str(palavra).strip().lower()
            if chave:
                visto = playbook["vocabulario"].setdefault(chave, [])
                if semana not in visto:
                    visto.append(semana)

    for nome in ("padroes", "vozes", "aberturas"):
        playbook[nome].sort(key=lambda e: (-len(e["semanas"]), e["semanas"][-1]))
    return playbook


def _viva(entrada: dict, hoje: date) -> bool:
    ultima = date.fromisoformat(entrada["semanas"][-1])
    return (hoje - ultima).days <= SEMANAS_ATE_DORMIR * 7


def classificar(playbook: dict, hoje: date | None = None) -> dict:
    """Separa cada categoria em consolidado / em observação (o dormente fica fora)."""
    hoje = hoje or date.today()
    saida = {}
    for nome in ("padroes", "vozes", "aberturas"):
        vivas = [e for e in playbook[nome] if _viva(e, hoje)][:MAX_POR_LISTA]
        saida[nome] = {
            "consolidado": [e for e in vivas if len(e["semanas"]) >= 2],
            "em_observacao": [e for e in vivas if len(e["semanas"]) == 1],
        }
    vocab = sorted(playbook["vocabulario"].items(), key=lambda kv: -len(kv[1]))
    saida["vocabulario"] = [p for p, s in vocab if len(s) >= 2][:30]
    return saida


def resumo_para_pesquisa(playbook: dict) -> dict:
    """Versão compacta para a etapa de pesquisa reconhecer o já sabido."""
    c = classificar(playbook)
    return {
        "semanas_de_historico": len(playbook["semanas"]),
        "padroes_consolidados": [f"{e['texto']} ({len(e['semanas'])} sem.)"
                                 for e in c["padroes"]["consolidado"][:15]],
        "vozes_consolidadas": [f"{e['texto']} ({len(e['semanas'])} sem.)"
                               for e in c["vozes"]["consolidado"][:10]],
        "em_observacao": [e["texto"] for e in c["padroes"]["em_observacao"][:8]],
    }


def resumo_para_escrita(playbook: dict) -> dict:
    """Versão para o roteirista: estruturas, vozes e aberturas com exemplos."""
    c = classificar(playbook)

    def item(e):
        d = {"texto": e["texto"], "semanas": len(e["semanas"])}
        if e.get("evidencias"):
            d["exemplos"] = e["evidencias"][-2:]
        if e.get("metricas"):
            d["metricas"] = e["metricas"][-2:]
        return d

    return {
        "semanas_de_historico": len(playbook["semanas"]),
        "estruturas_comprovadas": [item(e) for e in c["padroes"]["consolidado"][:12]],
        "vozes_que_funcionam": [item(e) for e in c["vozes"]["consolidado"][:8]],
        "aberturas_que_prendem": [item(e) for e in c["aberturas"]["consolidado"][:10]],
        "vocabulario_do_nicho": c["vocabulario"][:25],
    }
