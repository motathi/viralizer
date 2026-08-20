"""Geração de ideias e roteiros embasados a partir dos virais descobertos.

Pipeline em duas etapas para equilibrar custo e qualidade:

1. PESQUISA (modelo barato — Haiku): analisa os sinais coletados e usa a
   busca web para verificar as trends atuais e localizar referências
   científicas reais, produzindo um briefing compacto de pautas.
2. ESCRITA (modelo forte — Opus): recebe o briefing pronto e escreve os
   roteiros finais em uma única passada, sem busca — é aqui que a
   qualidade do texto importa, e a entrada é pequena.
"""

import json
import re

import anthropic

MODELO_PESQUISA = "claude-haiku-4-5"
MODELO_ESCRITA = "claude-opus-5"
MAX_BUSCAS = 8

PROMPT_PESQUISA = """\
Você é um analista de conteúdo viral para nichos de saúde nas redes sociais.
Sua saída alimenta um roteirista — seja factual, compacto e verificável.

METODOLOGIA OBRIGATÓRIA (nesta ordem — os virais vêm primeiro, as ideias
derivam deles, nunca o contrário):

1. ESTUDE OS VIRAIS COLETADOS: você recebe vídeos e posts virais REAIS do
   nicho, com URL e métricas. Para cada um que for relevante ao nicho,
   identifique: o tema, o gancho usado, o formato, e POR QUE viralizou
   (identificação, polêmica, utilidade salvável, confissão, mito-desmontado,
   resposta a comentário...). Ignore os que não têm relação com o nicho.
   Só conta como viral de origem um sinal com desempenho realmente viral
   (dezenas de milhares de views ou milhares de interações) — nunca ancore
   uma pauta em post de alcance baixo, por mais "qualificado" que pareça.
   VIRAIS EM OUTROS IDIOMAS (inglês, espanhol) são especialmente valiosos:
   um tema que estourou lá fora e ainda não tem versão forte em português
   do Brasil é uma janela de oportunidade — a pauta derivada deve ADAPTAR
   culturalmente o tema e a mecânica para o público brasileiro (nunca
   traduzir literalmente) e registrar isso no campo por_que_viralizou
   (ex.: "viral em inglês, 4M views, sem versão BR consolidada").
2. SINTETIZE OS PADRÕES VENCEDORES da semana: quais mecânicas de gancho,
   temas e formatos se repetem entre os virais de melhor desempenho.
3. DERIVE AS PAUTAS DOS VIRAIS: cada pauta DEVE nascer de um ou mais virais
   analisados — copie as URLs exatas dos virais de origem — e aplicar o
   padrão identificado, adaptado ao perfil profissional (autoridade médica,
   não criador comum). É PROIBIDO criar pauta sem viral de origem da coleta.
   Se os sinais não sustentarem a quantidade pedida com respaldo real, gere
   menos pautas: qualidade e rastreabilidade valem mais que quantidade.
4. Use a busca web APENAS para: confirmar tendências que os virais indicam e
   encontrar referências científicas reais para as afirmações que cada pauta
   vai exigir (priorize SBD, CFM e revistas indexadas; copie título e link
   exatos). NUNCA invente referência: sem fonte confiável, descarte a pauta.

Responda SOMENTE com um JSON válido:
{
  "padroes_da_semana": [
    {"padrao": "mecânica identificada", "evidencia": "quais virais a sustentam, com métricas"}
  ],
  "pautas": [
    {
      "tema": "...",
      "pilar": "um dos pilares do nicho",
      "angulo": "o ângulo específico que diferencia esta pauta",
      "plataforma_origem": "tiktok | instagram | youtube | multiplataforma",
      "padrao_aplicado": "qual padrão vencedor esta pauta aplica e como",
      "virais_origem": [
        {"url": "URL exata do sinal coletado", "autor": "...", "metrica": "ex.: 2.8M views, 6% engaj.", "por_que_viralizou": "..."}
      ],
      "referencias": [{"titulo": "...", "fonte": "...", "url": "..."}]
    }
  ]
}
Distribua as pautas entre os pilares, sem repetir tema.

MEMÓRIA (anti-repetição): o campo "ja_publicado" traz temas e ganchos já
usados em semanas anteriores. É PROIBIDO repetir ou apenas reformular
qualquer um deles — inclusive versões próximas da mesma tese (ex.: se já
houve "a ordem do skincare importa", não proponha "a ordem tem ciência").
Na dúvida sobre semelhança, descarte e escolha outro ângulo.
"""

PROMPT_ESCRITA = """\
Você é um roteirista sênior de conteúdo para redes sociais em nichos de
saúde, escrevendo para o perfil descrito abaixo. Você recebe um briefing de
pautas derivadas da análise de vídeos virais reais do nicho — cada pauta
traz os virais de origem e o padrão que a fez viralizar. Seu trabalho é
aplicar conscientemente esse padrão ao escrever o roteiro (mesma mecânica de
gancho e estrutura, adaptada à autoridade médica do perfil — sem copiar
texto). Não invente dados nem referências: use somente o que está no
briefing (pode reformular a redação, nunca o conteúdo factual). Copie os
campos virais_origem e padrao_aplicado da pauta para a ideia correspondente.

Regras de escrita (qualidade de produção):
- LINGUAGEM FALADA: escreva como a pessoa fala em voz alta — frases curtas,
  contrações ("pra", "tá"), ritmo de conversa. Se soa como texto de blog,
  reescreva.
- BLOCOS DE TEMPO: divida o roteiro de vídeo em blocos com marcação de
  segundos (0-3s, 3-15s, ...), pensando em retenção: gancho, um insight por
  bloco, fechamento com CTA.
- DIREÇÃO DE GRAVAÇÃO: para cada bloco, uma instrução curta de como gravar
  (enquadramento, corte, texto que aparece na tela).
- 3 GANCHOS por ideia, com ângulos distintos (pergunta, afirmação
  contraintuitiva, resposta a comentário/trend).
- VERSÃO CARROSSEL: capa com gancho curto, 5 a 7 lâminas com UMA ideia por
  lâmina, e lâmina final de CTA.
- LEGENDA PRONTA: 2 a 4 frases, primeira linha forte, sem hashtags.
- VARIEDADE: não repita gancho nem formato entre as ideias.

LIBERDADE TOTAL DE ESCRITA. Quem publica é uma profissional da área, com
autonomia e discernimento sobre o próprio conteúdo, e revisa cada roteiro
antes de gravar. O seu papel é entregar o melhor roteiro possível — não
policiar o que ela pode dizer.

Portanto: escreva com ousadia. Ganchos fortes, opinião firme, humor,
provocação, posicionamento claro, discordar de trends, dizer "isso não
funciona", contar bastidor. Não se autocensure, não amacie o texto por
precaução e não encha de ressalvas defensivas ("consulte sempre", "cada
caso é um caso") — use ressalva apenas quando ela acrescentar informação
real ao conteúdo. Se o perfil trouxer preferências pessoais na lista
"preferencias", respeite-as; fora isso, nada limita a sua escrita.

Responda SOMENTE com um JSON válido no formato:
{
  "ideias": [
    {
      "titulo": "...",
      "pilar": "...",
      "formato": "ex.: talking head com legenda dinâmica, POV, resposta a comentário...",
      "ganchos_3s": ["opção 1", "opção 2", "opção 3"],
      "roteiro_reels": [
        {"tempo": "0-3s", "fala": "...", "direcao": "..."}
      ],
      "roteiro_carrossel": {"capa": "...", "laminas": ["..."], "cta_final": "..."},
      "legenda_post": "...",
      "duracao_estimada_seg": 45,
      "plataforma_origem_da_tendencia": "tiktok | instagram | youtube | multiplataforma",
      "padrao_aplicado": "copiado da pauta",
      "virais_origem": [{"url": "...", "autor": "...", "metrica": "...", "por_que_viralizou": "..."}],
      "embasamento_viral": "por que tende a performar, com o sinal do briefing",
      "embasamento_cientifico": ["referência do briefing, com fonte e link"],
      "cta": "...",
      "hashtags": ["#..."]
    }
  ]
}
"""


def _extrair_json(texto: str) -> dict:
    """Extrai o objeto JSON da resposta, tolerando texto ao redor."""
    match = re.search(r"\{.*\}", texto, re.DOTALL)
    if not match:
        raise ValueError(f"Resposta sem JSON válido:\n{texto[:500]}")
    return json.loads(match.group(0))


def _rodar(client, *, modelo, system, conteudo, tools=None, max_tokens=16000,
           thinking=None) -> str:
    """Executa uma chamada em streaming, retomando turnos pausados (busca web)."""
    messages = [{"role": "user", "content": conteudo}]
    extras = {}
    if tools:
        extras["tools"] = tools
    if thinking:
        extras["thinking"] = thinking
    while True:
        with client.messages.stream(
            model=modelo, max_tokens=max_tokens, system=system,
            messages=messages, **extras,
        ) as stream:
            response = stream.get_final_message()
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue
        if response.stop_reason == "refusal":
            raise RuntimeError(
                "O modelo recusou a solicitação: "
                f"{getattr(response.stop_details, 'explanation', '')}"
            )
        return "".join(b.text for b in response.content if b.type == "text")


def _compactar_sinais(sinais: dict, max_por_fonte: int = 12) -> dict:
    """Limita o volume de sinais enviado à etapa de pesquisa."""
    return {fonte: itens[:max_por_fonte] for fonte, itens in sinais.items() if itens}


def _metrica_forte(metrica: str, minimo: float = 10000) -> bool:
    """True se a métrica textual indica desempenho viral de verdade.

    Interpreta formatos como "5.7M views", "120k", "2 mil salvamentos",
    "85000 views". "39 likes" ou "8.9% engajamento" não passam.
    """
    if not metrica:
        return False
    sufixos = {"m": 1_000_000, "mi": 1_000_000, "k": 1_000, "mil": 1_000}
    for num, suf in re.findall(r"(\d+(?:[.,]\d+)?)\s*(m\b|mi\b|k\b|mil\b)?",
                               metrica.lower()):
        valor = float(num.replace(",", ".")) * sufixos.get((suf or "").strip(), 1)
        if valor >= minimo:
            return True
    return False


def _filtrar_pautas_fracas(briefing: dict) -> dict:
    """Descarta pautas cuja melhor âncora não é viral de verdade.

    Garantia programática além do prompt: nenhuma ideia pode nascer de
    post de alcance baixo, ainda que o modelo o tenha racionalizado.
    """
    fortes, fracas = [], []
    for pauta in briefing.get("pautas", []):
        ancoras = pauta.get("virais_origem", [])
        if any(_metrica_forte(v.get("metrica", "")) for v in ancoras):
            fortes.append(pauta)
        else:
            fracas.append(pauta.get("tema", "?"))
    if fracas:
        print(f"       ⚠️  {len(fracas)} pauta(s) descartada(s) por âncora fraca: "
              + "; ".join(fracas))
    return {**briefing, "pautas": fortes}


def gerar_roteiros(config: dict, sinais: dict, historico: list | None = None) -> dict:
    """Gera as ideias/roteiros da semana em duas etapas (pesquisa + escrita)."""
    client = anthropic.Anthropic()
    quantidade = config["geracao"]["ideias_por_semana"]

    # Etapa 1 — pesquisa e curadoria com modelo barato + busca web
    pedido_pesquisa = {
        "nicho": config["nome"],
        "pilares": config["pilares"],
        "quantidade_de_pautas": quantidade,
        "sinais_coletados": _compactar_sinais(sinais),
        "ja_publicado": historico or [],
    }
    print(f"   [1/2] Pesquisa e curadoria ({MODELO_PESQUISA})...")
    briefing = _extrair_json(
        _rodar(
            client,
            modelo=MODELO_PESQUISA,
            system=PROMPT_PESQUISA,
            conteudo=json.dumps(pedido_pesquisa, ensure_ascii=False, indent=2),
            tools=[{"type": "web_search_20250305", "name": "web_search",
                    "max_uses": MAX_BUSCAS}],
            max_tokens=16000,
        )
    )
    briefing = _filtrar_pautas_fracas(briefing)
    if not briefing["pautas"]:
        raise RuntimeError(
            "Nenhuma pauta com âncora viral forte sobrou após o filtro — "
            "verifique a coleta de sinais antes de gastar com a escrita."
        )
    print(f"       {len(briefing['pautas'])} pautas com âncora viral verificada")

    # Etapa 2 — escrita dos roteiros com o modelo forte, sem busca
    pedido_escrita = {
        "nicho": config["nome"],
        "perfil": config["perfil"],
        "preferencias": config.get("preferencias", []),
        "quantidade_de_ideias": quantidade,
        "duracao_alvo_segundos": config["geracao"]["duracao_alvo_segundos"],
        "briefing": briefing,
    }
    print(f"   [2/2] Escrita dos roteiros ({MODELO_ESCRITA})...")
    return _extrair_json(
        _rodar(
            client,
            modelo=MODELO_ESCRITA,
            system=PROMPT_ESCRITA,
            conteudo=json.dumps(pedido_escrita, ensure_ascii=False, indent=2),
            thinking={"type": "adaptive"},
            max_tokens=64000,
        )
    )
