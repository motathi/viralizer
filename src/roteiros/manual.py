"""O manual de roteiros do nicho: o caderno destilado em prosa.

O caderno (playbook) é uma lista de contadores — útil para a máquina,
ruim para quem escreve. Aqui o modelo barato transforma o acumulado em um
manual legível: o que faz viralizar neste nicho, as estruturas comprovadas
com métrica, as vozes, as aberturas com exemplos literais, o vocabulário
e o que evitar. É o que o roteirista lê antes de escrever, e é o que a
pessoa pode abrir no painel para ver o que o radar aprendeu.
"""

import json
from datetime import date
from pathlib import Path

MAX_CARACTERES_NO_PROMPT = 7000  # o manual inteiro vai para a escrita, com teto

PROMPT_MANUAL = """\
Você redige o manual de roteiros de um nicho, a partir do que várias semanas
de análise de vídeos virais acumularam. O leitor é um roteirista sênior que
vai escrever os roteiros da próxima semana; ele precisa de regras
acionáveis, não de teoria.

Escreva em português do Brasil, em Markdown, com estas seções:

# Manual de roteiros — {nicho}
_uma linha com quantas semanas de virais sustentam este manual_

## O que faz viralizar neste nicho
3 a 6 frases-regra. Cada uma nasce de um padrão consolidado (visto em 2+
semanas). Diga o padrão e por que funciona. Cite métrica quando houver.

## Estruturas comprovadas
Lista. Cada item: a estrutura em uma linha + a evidência (semanas, métrica).
Só o consolidado. O que está em observação vai em uma sub-lista "Em
observação (visto uma vez)" — pode ser modinha.

## Vozes que funcionam
Cada registro (o personagem que fala) com uma frase sobre quando usar.

## Aberturas que prendem
Cada jogada de abertura com 1 exemplo literal entre aspas, quando houver.

## Vocabulário do nicho
As palavras concretas que os virais usam. Uma linha, separadas por vírgula.

## O que evitar
Derive do que as vozes evitam e do que nunca aparece nos virais.

{secao_preferencias}
Regras: não invente nada que não esteja nos dados; não repita o mesmo
ponto em duas seções; máximo de 900 palavras; nada de introdução ou
despedida.
"""

SECAO_PREFERENCIAS = """\
## Preferências da profissional
O que ela escolheu gravar e o que descartou nas semanas anteriores
(campo "preferencias"). Extraia 2 a 4 tendências de gosto — pilar, voz,
formato — e liste os assuntos descartados, para não voltar a propô-los.
"""


def _caminho(raiz: Path, nicho: str) -> Path:
    return raiz / "dados" / f"manual-{nicho}.md"


def carregar(raiz: Path, nicho: str) -> str:
    arquivo = _caminho(raiz, nicho)
    return arquivo.read_text(encoding="utf-8") if arquivo.exists() else ""


def salvar(raiz: Path, nicho: str, texto: str) -> Path:
    arquivo = _caminho(raiz, nicho)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(texto, encoding="utf-8")
    return arquivo


def destilar(client, config: dict, resumo_playbook: dict,
             preferencias: dict | None = None) -> str:
    """Escreve o manual a partir do caderno consolidado (modelo barato)."""
    from src.roteiros.gerador import MODELO_PESQUISA, _rodar  # evita import circular

    system = PROMPT_MANUAL.format(
        nicho=config["nome"],
        secao_preferencias=SECAO_PREFERENCIAS if preferencias else "",
    )
    pedido = {"nicho": config["nome"], "perfil": config.get("perfil", {}),
              "caderno": resumo_playbook}
    if preferencias:
        pedido["preferencias"] = preferencias
    texto = _rodar(client, modelo=MODELO_PESQUISA, system=system,
                   conteudo=json.dumps(pedido, ensure_ascii=False, indent=2),
                   max_tokens=3000).strip()
    rodape = (f"\n\n---\n_Atualizado em {date.today().isoformat()} · "
              f"{resumo_playbook.get('semanas_de_historico', 0)} semana(s) de virais analisados_\n")
    return texto + rodape


def para_prompt(texto: str) -> str:
    """O manual como vai para o roteirista, com teto de tamanho."""
    if len(texto) <= MAX_CARACTERES_NO_PROMPT:
        return texto
    return texto[:MAX_CARACTERES_NO_PROMPT] + "\n\n[manual truncado]"
