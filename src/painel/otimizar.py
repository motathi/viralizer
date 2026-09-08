"""Otimiza os termos de busca do nicho com base no histórico de resultados.

Lê o desempenho acumulado de cada termo, pede à IA (modelo barato) um
parecer sobre o que cortar e o que acrescentar, e aplica no arquivo do
nicho — dentro de travas que impedem a IA de esvaziar a configuração.

A IA opina; o código decide o que é permitido. Uso:
    python -m src.painel.otimizar --nicho dermatologia-estetica
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

import yaml
from dotenv import load_dotenv

from src.chaves import conferir_anthropic
from src.descoberta.termos import carregar, desempenho, sugestoes_recorrentes
from src.roteiros.gerador import MODELO_PESQUISA, _extrair_json, _rodar

RAIZ = Path(__file__).resolve().parent.parent.parent

MIN_RODADAS = 2          # sem duas coletas não há o que analisar
RODADAS_PARA_CORTAR = 3  # só corta termo com histórico suficiente
MAX_REMOCOES = 3
MAX_ADICOES = 4
MIN_PALAVRAS = 8         # nunca deixar a busca magra demais
MIN_HASHTAGS = 6
TERMO_VALIDO = re.compile(r"^[\wà-úÀ-Ú][\wà-úÀ-Ú '\-]{2,59}$")

PROMPT = """\
Você ajusta a lista de termos de busca de um radar de conteúdo viral.

Recebe o desempenho real de cada termo ao longo de várias coletas semanais:
quantas rodadas participou, quantos vídeos trouxe no total (coletados) e
quantos desses eram virais de verdade (virais, os que passaram no filtro de
views). Recebe também termos que os próprios virais do nicho usam e que
ainda não são monitorados.

Critérios:
- Cortar termo que participou de várias rodadas e não entregou viral nenhum.
  Termo que traz muito volume e nenhum viral é pior que termo que traz pouco
  volume e algum viral: volume sem viralidade é ruído.
- Não cortar termo com pouco histórico: pode ter sido azar de uma semana.
- Ao acrescentar, prefira frase a palavra solta — a intenção mora na frase.
  "acne" é assunto; "acne adulta o que fazer" é alguém pedindo ajuda.
  Evite palavra ambígua: a busca ignora acento, então "pele" traz o Pelé.
- Prefira termos com carga de conflito, dúvida, dinheiro, medo ou
  arrependimento — é disso que viral é feito.
- Mantenha variedade de idioma (PT, EN, ES) e não repita o que já existe.

Responda SOMENTE com JSON válido:
{
  "remover": [{"termo": "exatamente como aparece na lista atual", "motivo": "curto"}],
  "adicionar": [{"termo": "...", "tipo": "palavra | hashtag", "motivo": "curto"}],
  "resumo": "uma frase sobre o estado geral dos termos"
}
Se não houver o que mudar, devolva listas vazias e explique no resumo.
"""


def _rotulo(termo: str, tipo: str) -> str:
    """Como o termo aparece no histórico (o rótulo impresso na coleta)."""
    return f"#{termo.lstrip('#')}" if tipo == "hashtag" else f'"{termo}"'


def _substituir_lista(texto: str, chave: str, itens: list[str]) -> str:
    """Reescreve os itens de uma lista YAML, preservando o resto do arquivo.

    O bloco explicativo antes da chave fica intacto. Comentários que
    estavam entre os itens não têm mais a que se referir depois do
    reordenamento, então são recolhidos no topo da lista, rotulados —
    perder anotação de quem usa o arquivo seria pior que a bagunça.
    """
    linhas = texto.splitlines()
    try:
        inicio = next(i for i, l in enumerate(linhas) if l.startswith(f"{chave}:"))
    except StopIteration:
        return texto

    fim = inicio + 1
    comentarios = []
    while fim < len(linhas):
        atual = linhas[fim]
        if atual.strip().startswith("- "):
            fim += 1
        elif atual.strip().startswith("#") and atual.startswith(" "):
            marca = atual.strip()
            if not marca.startswith(("# ajustada pelo otimizador",
                                     "# anotações que estavam")):
                comentarios.append(marca)
            fim += 1
        elif not atual.strip():
            break
        else:
            break

    novo = [f"{chave}:", f"  # ajustada pelo otimizador em {date.today().isoformat()}"]
    if comentarios:
        novo.append("  # anotações que estavam entre os itens desta lista:")
        novo += [f"  {c}" for c in comentarios]
    novo += [f"  - {i}" for i in itens]
    return "\n".join(linhas[:inicio] + novo + linhas[fim:]) + "\n"


def _aplicar(config_texto: str, palavras: list[str], hashtags: list[str]) -> str:
    texto = _substituir_lista(config_texto, "buscas_por_palavra", palavras)
    return _substituir_lista(texto, "hashtags_monitoradas", hashtags)


def _limpar(termo: str) -> str:
    """Normaliza o que a IA devolveu: ela pode citar o rótulo do relatório
    ('"acne adulta"', '#skintok') em vez do item cru da lista."""
    return str(termo).strip().strip('"').strip("'").lstrip("#").strip()


def _valido(termo: str, tipo: str) -> bool:
    if not TERMO_VALIDO.match(termo):
        return False
    # frase, não palavra solta: "pele" traz o Pelé, "harmonização" traz
    # harmonização de cores. Hashtag é single-token por natureza.
    return tipo == "hashtag" or len(termo.split()) >= 2


def main() -> int:
    load_dotenv(RAIZ / ".env")
    parser = argparse.ArgumentParser(description="Otimiza os termos de busca")
    parser.add_argument("--nicho", required=True)
    args = parser.parse_args()

    caminho = RAIZ / "config" / "nichos" / f"{args.nicho}.yaml"
    if not caminho.exists():
        print(f"❌ Nicho '{args.nicho}' não encontrado.")
        return 1

    rodadas = carregar(RAIZ, args.nicho)
    if len(rodadas) < MIN_RODADAS:
        print(f"📊 Ainda não há histórico suficiente ({len(rodadas)} coleta(s)).")
        print(f"   Gere a agenda pelo menos {MIN_RODADAS} vezes — aí eu tenho o que")
        print("   comparar. Otimizar com uma semana só seria chute com mais passos.")
        return 0

    texto = caminho.read_text(encoding="utf-8")
    config = yaml.safe_load(texto)
    palavras = list(config.get("buscas_por_palavra", []))
    hashtags = [h.lstrip("#") for h in config.get("hashtags_monitoradas", [])]
    resumo = desempenho(rodadas)

    atuais = ([{"termo": p, "tipo": "palavra", **resumo.get(_rotulo(p, "palavra"),
                {"rodadas": 0, "coletados": 0, "virais": 0})} for p in palavras]
              + [{"termo": h, "tipo": "hashtag", **resumo.get(_rotulo(h, "hashtag"),
                  {"rodadas": 0, "coletados": 0, "virais": 0})} for h in hashtags])

    conferir_anthropic(RAIZ)
    print(f"🎯 Analisando {len(atuais)} termos sobre {len(rodadas)} coleta(s)...")
    pedido = {
        "nicho": config["nome"],
        "publico": config.get("perfil", {}).get("publico", ""),
        "termos_atuais": atuais,
        "sugeridos_pela_coleta": sugestoes_recorrentes(rodadas),
        "limites": {"remover_no_maximo": MAX_REMOCOES, "adicionar_no_maximo": MAX_ADICOES},
    }

    import anthropic
    parecer = _extrair_json(_rodar(
        anthropic.Anthropic(), modelo=MODELO_PESQUISA, system=PROMPT,
        conteudo=json.dumps(pedido, ensure_ascii=False, indent=2), max_tokens=4000))

    # ── travas: a IA opina, o código decide ────────────────────────────
    removidos, recusados = [], []
    for item in parecer.get("remover", []):
        if len(removidos) >= MAX_REMOCOES:
            break
        termo = str(item.get("termo", "")).strip()
        alvo = _limpar(termo)
        if alvo in palavras:
            tipo, lista, minimo = "palavra", palavras, MIN_PALAVRAS
        elif alvo in hashtags:
            tipo, lista, minimo = "hashtag", hashtags, MIN_HASHTAGS
        else:
            recusados.append(f"{termo} (não está na lista atual)")
            continue
        hist = resumo.get(_rotulo(alvo, tipo), {})
        if hist.get("rodadas", 0) < RODADAS_PARA_CORTAR:
            recusados.append(f"{termo} (só {hist.get('rodadas', 0)} coleta(s) de histórico)")
            continue
        if hist.get("virais", 0) > 0:
            recusados.append(f"{termo} (já entregou {hist['virais']} viral/is)")
            continue
        if len(lista) - 1 < minimo:
            recusados.append(f"{termo} (a lista ficaria curta demais)")
            continue
        lista.remove(alvo)
        removidos.append((termo, item.get("motivo", "")))

    adicionados = []
    for item in parecer.get("adicionar", []):
        if len(adicionados) >= MAX_ADICOES:
            break
        termo = str(item.get("termo", "")).strip()
        alvo = _limpar(termo)
        tipo = "hashtag" if (item.get("tipo") == "hashtag" or termo.startswith("#")) \
            else "palavra"
        if alvo in palavras or alvo in hashtags:
            recusados.append(f"{termo} (já existe)")
            continue
        if not _valido(alvo, tipo):
            recusados.append(f"{termo} (palavra solta ou formato inválido)")
            continue
        (hashtags if tipo == "hashtag" else palavras).append(alvo)
        adicionados.append((termo, item.get("motivo", "")))

    if not removidos and not adicionados:
        print("✅ Nada a mudar — os termos atuais estão dando conta.")
        if parecer.get("resumo"):
            print(f"   {parecer['resumo']}")
        if recusados:
            print("   Sugestões recusadas pelas travas: " + "; ".join(recusados))
        return 0

    caminho.with_suffix(".yaml.anterior").write_text(texto, encoding="utf-8")
    caminho.write_text(_aplicar(texto, palavras, hashtags), encoding="utf-8")

    print()
    for termo, motivo in removidos:
        print(f"   ➖ {termo} — {motivo}")
    for termo, motivo in adicionados:
        print(f"   ➕ {termo} — {motivo}")
    if recusados:
        print("\n   🔒 Recusado pelas travas: " + "; ".join(recusados))
    print(f"\n✅ {len(palavras)} palavras e {len(hashtags)} hashtags agora.")
    print(f"   A versão anterior ficou em {caminho.name}.anterior, se quiser voltar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
