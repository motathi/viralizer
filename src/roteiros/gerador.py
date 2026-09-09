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
from collections import Counter
from pathlib import Path

import anthropic

from src.feedback import preferencias as preferencias_reveladas
from src.roteiros import manual as manual_mod
from src.roteiros import playbook as pb
from src.texto import parecidos, tokens as _tokens

MODELO_PESQUISA = "claude-haiku-4-5"
MODELO_ESCRITA = "claude-opus-5"
MAX_BUSCAS = 8

PROMPT_PESQUISA = """\
Você é um analista de conteúdo viral para nichos de saúde nas redes sociais.
Sua saída alimenta um roteirista — seja factual, compacto e verificável.

METODOLOGIA OBRIGATÓRIA (nesta ordem — os virais vêm primeiro, as ideias
derivam deles, nunca o contrário):

1. ESTUDE OS VIRAIS COLETADOS: você recebe vídeos e posts virais REAIS do
   nicho, com URL e métricas. Para cada um relevante, identifique: o tema, o
   gancho usado, o formato, e POR QUE viralizou (identificação, polêmica,
   utilidade salvável, confissão, mito-desmontado, resposta a comentário...).
   Ignore os que não têm relação com o nicho.
   O campo "origem_busca" diz como cada viral foi encontrado: "hashtag" (a
   comunidade marcou), "palavra" (viralizou sem usar hashtag do nicho —
   costuma ter alcance mais amplo, fora da bolha) ou "perfil" (referência do
   nicho). Dê atenção especial aos de origem "palavra": alcançam gente além
   de quem já segue o assunto.
   Só conta como viral de origem um sinal com desempenho realmente viral
   (dezenas de milhares de views ou milhares de interações) — nunca ancore
   uma pauta em post de alcance baixo, por mais "qualificado" que pareça.
   VIRAIS EM OUTROS IDIOMAS (inglês, espanhol) são especialmente valiosos:
   um tema que estourou lá fora e ainda não tem versão forte em português
   do Brasil é uma janela de oportunidade — a pauta derivada deve ADAPTAR
   culturalmente o tema e a mecânica para o público brasileiro (nunca
   traduzir literalmente) e registrar isso no campo por_que_viralizou
   (ex.: "viral em inglês, 4M views, sem versão BR consolidada").
2. DECIFRE A LINGUAGEM DE CADA VIRAL — esta etapa vale tanto quanto o tema.
   O que faz o vídeo colar não é só o assunto: é COMO ele é dito. Duas
   pessoas dando a mesma informação têm resultados opostos por causa disso.
   A prova está no campo "descricao" de cada sinal (a legenda e o texto na
   tela, literais). Use também a busca web quando precisar ouvir mais do
   vídeo. Para cada viral relevante, registre:
   - fala_literal: 1 a 3 trechos COPIADOS ao pé da letra. Nunca parafraseie
     aqui — é a evidência bruta, e é dela que o roteirista tira o ouvido.
   - registro: o papel de quem fala ("amiga que conta segredo", "professora
     irritada", "perita indignada com o mercado", "confissão de bastidor",
     "quem já errou e avisa"). Registro não é tom genérico: é um personagem.
   - abertura: a jogada exata das primeiras palavras ("Para de...",
     "Ninguém te falou que...", "Se você faz isso, para agora").
   - tratamento: como fala com quem assiste (você, vocês, a gente, imperativo,
     pergunta direta, acusação amigável).
   - ritmo: comprimento das frases, repetição, corte seco, pausa antes do
     ponto, enumeração.
   - vocabulario: 3 a 8 palavras/expressões concretas que ESSE viral usa —
     gíria, apelido de procedimento, termo técnico já popularizado.
   - o_que_evita: o que essa voz nunca faz (jargão, ressalva, formalidade,
     saudação, aquecimento antes do assunto).
3. SINTETIZE OS PADRÕES VENCEDORES da semana: quais mecânicas de gancho,
   temas, formatos E VOZES se repetem entre os virais de melhor desempenho.
4. DERIVE AS PAUTAS DOS VIRAIS: cada pauta DEVE nascer de um ou mais virais
   analisados — copie as URLs exatas dos virais de origem — e aplicar o
   padrão identificado, adaptado ao perfil profissional (autoridade médica,
   não criador comum). É PROIBIDO criar pauta sem viral de origem da coleta.
   Cada pauta herda a LINGUAGEM do viral que a originou: preencha o campo
   "linguagem" copiando o registro, a abertura, o tratamento, o ritmo, o
   vocabulário e o o_que_evita daquele viral, mais os trechos literais. É
   com isso que o roteirista vai escrever — sem esse campo, o roteiro sai
   sem sal. Pautas diferentes devem trazer vozes diferentes.
   Se os sinais não sustentarem a quantidade pedida com respaldo real, gere
   menos pautas: qualidade e rastreabilidade valem mais que quantidade.
5. Use a busca web APENAS para: confirmar tendências que os virais indicam e
   encontrar referências científicas reais para as afirmações que cada pauta
   vai exigir (priorize SBD, CFM e revistas indexadas; copie título e link
   exatos). NUNCA invente referência: sem fonte confiável, descarte a pauta.

Responda SOMENTE com um JSON válido:
{
  "padroes_da_semana": [
    {"padrao": "mecânica identificada", "evidencia": "quais virais a sustentam, com métricas"}
  ],
  "vozes_da_semana": [
    {"registro": "o personagem que está funcionando", "evidencia": "virais que o usam, com métricas"}
  ],
  "pautas": [
    {
      "tema": "...",
      "pilar": "um dos pilares do nicho",
      "angulo": "o ângulo específico que diferencia esta pauta",
      "plataforma_origem": "tiktok | instagram | youtube | multiplataforma",
      "padrao_aplicado": "qual padrão vencedor esta pauta aplica e como",
      "virais_origem": [
        {"url": "URL exata do sinal coletado", "autor": "...", "metrica": "ex.: 2.8M views, 6% engaj.", "por_que_viralizou": "...", "fala_literal": "trecho copiado ao pé da letra do viral"}
      ],
      "linguagem": {
        "registro": "o personagem que fala",
        "abertura": "a jogada das primeiras palavras, a imitar",
        "tratamento": "...",
        "ritmo": "...",
        "vocabulario": ["palavra concreta do viral", "..."],
        "o_que_evita": "...",
        "trechos_literais": ["copiado do viral, sem parafrasear", "..."]
      },
      "referencias": [{"titulo": "...", "fonte": "...", "url": "..."}]
    }
  ]
}
Distribua as pautas entre os pilares, sem repetir tema.

DIVERSIDADE DE ASSUNTO (regra dura): no máximo 2 pautas podem girar em torno
do mesmo assunto central — mesmo ativo, mesmo procedimento, mesma condição.
Dez ângulos do peróxido de benzoíla é uma agenda ruim, ainda que ele seja o
viral da semana. Se os sinais estiverem dominados por um único assunto, use
os sinais dos demais assuntos mesmo que tenham métrica menor (desde que
ainda virais), ou entregue menos pautas. Variedade de assunto vale mais que
métrica bruta.

CONHECIMENTO ACUMULADO: o campo "conhecimento_acumulado" traz o que as
pesquisas das semanas anteriores já consolidaram (padrões e vozes vistos em
2+ semanas) e o que está em observação. Use para separar o estrutural do
passageiro: um padrão consolidado que se repete esta semana é regra do
nicho; um que sumiu merece nota ("padrão X não apareceu esta semana"); algo
que não está lá é NOVO e deve ser destacado como tal no padroes_da_semana.
Não deixe o acumulado te cegar: os virais desta semana mandam.

MEMÓRIA (anti-repetição): o campo "ja_publicado" traz temas e ganchos já
usados em semanas anteriores. É PROIBIDO repetir ou apenas reformular
qualquer um deles — inclusive versões próximas da mesma tese (ex.: se já
houve "a ordem do skincare importa", não proponha "a ordem tem ciência").
Na dúvida sobre semelhança, descarte e escolha outro ângulo.
"""

REGRAS_SEM_SAL = """\
PROIBIDO — é exatamente isto que deixa roteiro sem sal:
- Aquecimento antes do assunto. Nada de "Você sabia que", "Vamos falar
  sobre", "Hoje eu vou te contar", "Muita gente me pergunta", "Bora lá".
  A primeira frase JÁ É o assunto.
- Adjetivo vago onde cabe coisa concreta. "Muito eficaz" não diz nada;
  "clareia em 8 semanas", "custa o preço de um jantar", "arde como pimenta"
  dizem. Todo gancho precisa de pelo menos um destes: um número, uma imagem
  física, o nome de um produto/procedimento, ou uma afirmação com a qual
  dê para discordar.
- Frases todas do mesmo comprimento. Alterne: uma longa que constrói, uma
  curta que derruba. É o ritmo que segura, não a informação.
- Encerrar sempre igual. Se todo roteiro termina em "salva esse post",
  você escreveu um só roteiro dez vezes.
- Ressalva defensiva ("cada caso é um caso", "procure seu dermatologista")
  colada por precaução. Só entra se acrescentar informação real.
- Neutralidade. Todo roteiro precisa de pelo menos uma frase em que ela
  toma partido: o que ela faria, o que ela não faz, com o que ela não
  concorda. Conteúdo que não arrisca nada não é assistido até o fim.
"""

LIBERDADE_EDITORIAL = """\
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
"""

PROMPT_ESCRITA_MOLDE = """\
Você é um roteirista sênior de conteúdo para redes sociais em nichos de
saúde, escrevendo para o perfil descrito abaixo. Você recebe um briefing de
pautas derivadas da análise de vídeos virais reais do nicho — cada pauta
traz os virais de origem, o padrão que a fez viralizar e a LINGUAGEM em que
ela foi contada. Seu trabalho é aplicar conscientemente esse padrão E essa
linguagem ao escrever o roteiro (mesma mecânica de gancho, mesma voz,
adaptadas à autoridade médica do perfil — sem copiar texto). Não invente dados nem referências: use somente o que está no
briefing (pode reformular a redação, nunca o conteúdo factual). Copie os
campos virais_origem e padrao_aplicado da pauta para a ideia correspondente.

MANUAL DO NICHO: o campo "manual_do_nicho" é o conhecimento acumulado de
várias semanas de virais deste nicho — estruturas comprovadas com métrica,
vozes, aberturas com exemplos literais, vocabulário, o que evitar. Leia
antes de escrever e use as estruturas comprovadas. Não é regra rígida: o
briefing desta semana manda quando conflitar, e o manual não substitui a
linguagem de cada pauta — ele afina o ouvido, a pauta dá a voz.

PREFERÊNCIAS REVELADAS: se vier o campo "preferencias_reveladas", é o que
ela escolheu gravar e o que descartou nas semanas anteriores. Trate como
sinal de gosto, não como regra: pese a favor do que ela escolhe, e não
proponha nada parecido com os assuntos descartados.

A VOZ É PARTE DA PAUTA — leia isto antes de tudo.
Cada pauta traz um campo "linguagem" decifrado do viral que a originou:
registro (o personagem que fala), abertura, tratamento, ritmo, vocabulário,
o que aquela voz evita, e "trechos_literais" copiados do viral.

- Escreva CADA roteiro na voz da SUA pauta, nunca numa voz média da casa.
  Se você trocar os títulos de dois roteiros e ninguém notar a diferença de
  quem está falando, os dois estão errados.
- Use os trechos_literais como afinação de ouvido: imite a construção da
  frase, o ritmo e o nível de informalidade. Nunca copie a frase em si.
- Use o vocabulário daquela voz. As palavras concretas que o viral usou
  valem mais que sinônimos "mais corretos".
- Respeite o o_que_evita da voz. Se ela não dá bom-dia, você não dá.
- VARIEDADE DE VOZ: não repita registro entre as ideias da semana.

{REGRAS_SEM_SAL}
Demais regras de escrita (qualidade de produção):
- LINGUAGEM FALADA: escreva como a pessoa fala em voz alta — frases curtas,
  contrações ("pra", "tá"), ritmo de conversa. Se soa como texto de blog,
  reescreva.
- BLOCOS DE TEMPO: divida o roteiro de vídeo em blocos com marcação de
  segundos (0-3s, 3-15s, ...), pensando em retenção: gancho, um insight por
  bloco, fechamento com CTA.
- DIREÇÃO DE GRAVAÇÃO: para cada bloco, uma instrução curta de como gravar
  (enquadramento, corte, texto que aparece na tela).
- 3 GANCHOS por ideia, com ângulos distintos (pergunta, afirmação
  contraintuitiva, resposta a comentário/trend) — todos na voz da pauta,
  e pelo menos um deles usando a jogada de abertura do campo "linguagem".
- VERSÃO CARROSSEL: capa com gancho curto, 5 a 7 lâminas com UMA ideia por
  lâmina, e lâmina final de CTA.
- LEGENDA PRONTA: 2 a 4 frases, primeira linha forte, sem hashtags.
- VARIEDADE: não repita gancho nem formato entre as ideias.

{LIBERDADE_EDITORIAL}
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
      "voz": {"registro": "o personagem em que este roteiro foi escrito",
              "de_onde_veio": "qual viral de origem ditou essa voz e o que dele você imitou"},
      "virais_origem": [{"url": "...", "autor": "...", "metrica": "...", "por_que_viralizou": "..."}],
      "embasamento_viral": "por que tende a performar, com o sinal do briefing",
      "embasamento_cientifico": ["referência do briefing, com fonte e link"],
      "cta": "...",
      "hashtags": ["#..."]
    }
  ]
}
"""

PROMPT_ESCRITA = (PROMPT_ESCRITA_MOLDE.replace("{REGRAS_SEM_SAL}", REGRAS_SEM_SAL)
                  .replace("{LIBERDADE_EDITORIAL}", LIBERDADE_EDITORIAL))


def _extrair_json(texto: str) -> dict:
    """Extrai o objeto JSON da resposta, tolerando texto e ruído ao redor.

    O modelo às vezes devolve preâmbulo, cerca de markdown ou mais de um
    objeto; aqui varremos os candidatos e ficamos com o maior objeto válido
    que contenha conteúdo útil.
    """
    limpo = texto.strip()
    if limpo.startswith("```"):  # cerca de markdown
        limpo = re.sub(r"^```[a-z]*\n?|```$", "", limpo, flags=re.MULTILINE).strip()

    decoder = json.JSONDecoder()
    candidatos = []
    for i, ch in enumerate(limpo):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(limpo[i:])
        except ValueError:
            continue
        if isinstance(obj, dict) and obj:
            candidatos.append(obj)
    if not candidatos:
        raise ValueError(f"Resposta sem JSON válido:\n{texto[:800]}")
    return max(candidatos, key=lambda o: len(json.dumps(o)))


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


def _mesmo_assunto(a: set, b: set, limite: float) -> bool:
    return parecidos(a, b, limite)


def _selecionar_variado(itens: list, limite: int, max_por_autor: int = 2,
                        sobreposicao: float = 0.34) -> list:
    """Escolhe sinais variados, não só os mais vistos.

    Cortar pelo topo puro entrega uma agenda inteira sobre a trend da
    semana — dez ângulos do mesmo assunto. Aqui cada sinal escolhido
    precisa trazer assunto novo em relação aos já escolhidos, e nenhum
    perfil ocupa a lista sozinho. A segunda passada preenche a cota sem a
    exigência de novidade, para nunca devolver menos do que cabe.
    """
    candidatos = [(v, _tokens(v.get("descricao", ""))) for v in itens]
    escolhidos: list[tuple[dict, set]] = []
    usados: set = set()
    por_autor: Counter = Counter()

    for exigir_novidade in (True, False):
        for video, toks in candidatos:
            if len(escolhidos) >= limite:
                break
            chave = video.get("url") or id(video)
            if chave in usados:
                continue
            autor = video.get("autor", "")
            if autor and por_autor[autor] >= max_por_autor:
                continue
            if exigir_novidade and any(_mesmo_assunto(toks, t, sobreposicao)
                                       for _, t in escolhidos):
                continue
            escolhidos.append((video, toks))
            usados.add(chave)
            por_autor[autor] += 1
    return [v for v, _ in escolhidos]


def _compactar_sinais(sinais: dict, max_por_fonte: int = 45) -> dict:
    """Escolhe quais sinais vão para a etapa de pesquisa.

    O limite é de orçamento (entrada do modelo barato), mas o critério é
    de variedade: sem isso a agenda inteira sai sobre um assunto só.
    """
    return {fonte: _selecionar_variado(itens, max_por_fonte)
            for fonte, itens in sinais.items() if itens}


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


# Aberturas de aquecimento: a frase gasta antes de o assunto começar.
ABERTURAS_MORTAS = re.compile(
    r"^\s*(você sabia|voce sabia|vamos falar|hoje eu vou|hoje vou|bora lá|bora la|"
    r"muita gente me pergunta|se liga|oi, gente|olá, pessoal|ola, pessoal|"
    r"eu vou te contar|deixa eu te contar|vem comigo)", re.IGNORECASE)


def _conferir_voz(roteiros: dict) -> None:
    """Avisa quando a escrita caiu na voz média da casa.

    O prompt pede voz distinta por ideia; aqui conferimos o resultado, para
    a falha aparecer no painel em vez de virar dez roteiros sem sal.
    """
    ideias = roteiros.get("ideias", [])
    registros, mortas, sem_voz = [], [], 0
    for ideia in ideias:
        voz = (ideia.get("voz") or {}).get("registro", "").strip().lower()
        if voz:
            registros.append(voz)
        else:
            sem_voz += 1
        for gancho in ideia.get("ganchos_3s", []):
            if gancho and ABERTURAS_MORTAS.match(gancho):
                mortas.append(gancho[:60])

    repetidos = len(registros) - len(set(registros))
    if repetidos:
        print(f"       ⚠️  {repetidos} ideia(s) repetem o mesmo registro de voz")
    if sem_voz:
        print(f"       ⚠️  {sem_voz} ideia(s) sem voz declarada")
    if mortas:
        print(f"       ⚠️  {len(mortas)} gancho(s) com abertura de aquecimento: "
              + "; ".join(mortas[:3]))
    if registros and not (repetidos or sem_voz or mortas):
        print(f"       {len(set(registros))} vozes distintas nas {len(ideias)} ideias")


def _conferir_variedade(briefing: dict) -> None:
    """Avisa quando a semana virou monotema.

    O prompt limita a 2 pautas por assunto; aqui conferimos o resultado,
    para a falha aparecer no painel em vez de virar dez variações da
    mesma ideia.
    """
    pautas = [(p.get("tema", ""), _tokens(p.get("tema", "")))
              for p in briefing.get("pautas", [])]
    grupos: Counter = Counter()
    for i, (_, toks) in enumerate(pautas):
        for j, (_, outros) in enumerate(pautas):
            if i < j and _mesmo_assunto(toks, outros, 0.25):
                grupos[i] += 1
    repetidas = sum(1 for n in grupos.values() if n)
    if repetidas > 2:
        print(f"       ⚠️  {repetidas} pautas giram em torno do mesmo assunto — "
              "a coleta desta semana pode ter vindo dominada por uma trend só")


def gerar_roteiros(config: dict, sinais: dict, historico: list | None = None,
                   raiz: Path | None = None, nicho: str | None = None) -> dict:
    """Gera as ideias/roteiros da semana em duas etapas (pesquisa + escrita).

    Com `raiz` e `nicho`, o caderno de aprendizado entra na pesquisa, absorve
    o que ela descobriu, vira manual e chega ao roteirista — é assim que a
    semana seguinte começa de onde esta parou.
    """
    client = anthropic.Anthropic()
    quantidade = config["geracao"]["ideias_por_semana"]
    aprende = raiz is not None and nicho is not None
    caderno = pb.carregar(raiz, nicho) if aprende else pb.vazio()

    # Etapa 1 — pesquisa e curadoria com modelo barato + busca web
    pedido_pesquisa = {
        "nicho": config["nome"],
        "pilares": config["pilares"],
        "quantidade_de_pautas": quantidade,
        "sinais_coletados": _compactar_sinais(sinais),
        "ja_publicado": historico or [],
        "conhecimento_acumulado": pb.resumo_para_pesquisa(caderno),
    }
    if caderno["semanas"]:
        print(f"📘 Caderno do nicho: {len(caderno['semanas'])} semana(s) de aprendizado")
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
    sem_linguagem = [p["tema"] for p in briefing["pautas"] if not p.get("linguagem")]
    if sem_linguagem:
        print(f"       ⚠️  {len(sem_linguagem)} pauta(s) sem linguagem decifrada — "
              "o roteiro delas tende a sair sem sal")
    _conferir_variedade(briefing)
    print(f"       {len(briefing['pautas'])} pautas com âncora viral verificada")

    # o que a pesquisa descobriu entra no caderno e vira manual
    manual_texto = ""
    prefs = None
    if aprende:
        pb.absorver(caderno, briefing)
        pb.salvar(raiz, nicho, caderno)
        prefs = preferencias_reveladas(raiz, nicho)
        print(f"   [📘] Destilando o manual do nicho ({MODELO_PESQUISA})...")
        try:
            manual_texto = manual_mod.destilar(client, config, pb.resumo_para_escrita(caderno), prefs)
            manual_mod.salvar(raiz, nicho, manual_texto)
            c = pb.classificar(caderno)
            print(f"        {len(c['padroes']['consolidado'])} estruturas consolidadas, "
                  f"{len(c['padroes']['em_observacao'])} em observação")
        except Exception as e:  # noqa: BLE001 - o manual é apoio, não pode travar a semana
            print(f"        (manual não atualizado: {type(e).__name__}) — usando o anterior")
            manual_texto = manual_mod.carregar(raiz, nicho)

    # Etapa 2 — escrita dos roteiros com o modelo forte, sem busca
    pedido_escrita = {
        "nicho": config["nome"],
        "perfil": config["perfil"],
        "preferencias": config.get("preferencias", []),
        "quantidade_de_ideias": quantidade,
        "duracao_alvo_segundos": config["geracao"]["duracao_alvo_segundos"],
        "briefing": briefing,
    }
    if manual_texto:
        pedido_escrita["manual_do_nicho"] = manual_mod.para_prompt(manual_texto)
    if prefs:
        pedido_escrita["preferencias_reveladas"] = prefs
    print(f"   [2/2] Escrita dos roteiros ({MODELO_ESCRITA})...")
    roteiros = _extrair_json(
        _rodar(
            client,
            modelo=MODELO_ESCRITA,
            system=PROMPT_ESCRITA,
            conteudo=json.dumps(pedido_escrita, ensure_ascii=False, indent=2),
            thinking={"type": "adaptive"},
            max_tokens=64000,
        )
    )
    _conferir_voz(roteiros)
    return roteiros
