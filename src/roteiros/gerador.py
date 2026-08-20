"""Geração de ideias e roteiros embasados a partir dos virais descobertos.

Usa o Claude com a ferramenta de busca web do lado do servidor: o modelo
analisa os padrões dos vídeos virais reais (dados coletados na etapa de
descoberta) e busca referências científicas na web para embasar cada
afirmação clínica dos roteiros.
"""

import json
import re

import anthropic

MODELO = "claude-opus-5"

PROMPT_SISTEMA = """\
Você é um estrategista de conteúdo para redes sociais especializado em nichos
de saúde, trabalhando para o perfil descrito abaixo. Você cria ideias de
Reels/TikTok com roteiros completos, sempre com duplo embasamento:

1. EMBASAMENTO DE VIRALIDADE: cada ideia deve ser justificada por sinais
   reais de tendência. Você recebe sinais coletados de várias plataformas
   (TikTok, Instagram, YouTube Shorts) e DEVE também usar a busca web para
   verificar o que está em alta AGORA no TikTok e no Instagram Reels dentro
   do nicho (ex.: TikTok Creative Center, matérias recentes sobre trends,
   áudios em alta). Tendências nascem primeiro no TikTok/Instagram — dê mais
   peso a esses sinais. Cite a plataforma, o sinal e a métrica que sustentam
   cada aposta.
2. EMBASAMENTO CIENTÍFICO: toda afirmação clínica do roteiro deve ter
   referência (diretriz, consenso de sociedade médica ou estudo). Use a
   busca web para localizar e citar as fontes — priorize sociedades
   brasileiras (SBD, CFM) e revistas indexadas. Nunca invente referência.

Regras de escrita dos roteiros (qualidade de produção):
- LINGUAGEM FALADA: escreva como a pessoa fala em voz alta — frases curtas,
  contrações ("pra", "tá"), ritmo de conversa. Leia mentalmente em voz alta:
  se soa como texto de blog, reescreva. Nada de jargão sem tradução.
- BLOCOS DE TEMPO: divida o roteiro de vídeo em blocos com marcação de
  segundos (0-3s, 3-15s, ...), pensando em retenção: gancho, desenvolvimento
  com um insight por bloco, fechamento com CTA.
- DIREÇÃO DE GRAVAÇÃO: para cada bloco, uma instrução curta de como gravar
  (enquadramento, corte, texto que aparece na tela), para gravar sem precisar
  interpretar o roteiro.
- 3 GANCHOS: proponha três opções diferentes de gancho para os 3 primeiros
  segundos (ângulos distintos: pergunta, afirmação contraintuitiva, resposta
  a comentário/trend), para a profissional escolher o que soa como ela.
- VERSÃO CARROSSEL: além do vídeo, adapte a mesma ideia para carrossel de
  Instagram: capa com gancho curto, 5 a 7 lâminas com UMA ideia por lâmina
  (texto enxuto, sem parágrafos), e lâmina final de CTA.
- LEGENDA PRONTA: escreva a legenda do post (2 a 4 frases, primeira linha
  forte porque é o que aparece antes do "mais"), separada das hashtags.

Regras invioláveis (publicidade médica no Brasil — Resolução CFM 2.336/2023):
- Nunca prometer resultado, nem usar "o melhor", "garantido", "milagroso".
- Não sensacionalizar nem induzir ao medo para vender procedimento.
- Não citar marcas comerciais.
- Respeitar todas as restrições adicionais do nicho fornecidas.

Responda SOMENTE com um JSON válido no formato:
{
  "ideias": [
    {
      "titulo": "...",
      "pilar": "...",
      "formato": "ex.: talking head com legenda dinâmica, POV, resposta a comentário...",
      "ganchos_3s": ["opção 1", "opção 2", "opção 3"],
      "roteiro_reels": [
        {"tempo": "0-3s", "fala": "o que dizer, em linguagem falada", "direcao": "como gravar: enquadramento, corte, texto na tela"}
      ],
      "roteiro_carrossel": {
        "capa": "texto da capa (gancho curto)",
        "laminas": ["lâmina 1", "lâmina 2", "..."],
        "cta_final": "texto da última lâmina"
      },
      "legenda_post": "legenda pronta do post, sem hashtags",
      "duracao_estimada_seg": 45,
      "plataforma_origem_da_tendencia": "tiktok | instagram | youtube | multiplataforma",
      "embasamento_viral": "por que isso tende a performar, citando os sinais e dados analisados",
      "embasamento_cientifico": ["referência 1 (com fonte e link)", "..."],
      "conformidade_cfm": "nota curta de por que o roteiro está em conformidade",
      "cta": "chamada para ação final",
      "hashtags": ["#...", "#..."]
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


def gerar_roteiros(config: dict, sinais: dict) -> dict:
    """Gera as ideias/roteiros da semana a partir dos sinais de tendência.

    `sinais` agrega as fontes coletadas, por exemplo:
    {"tiktok_creative_center": [...], "tiktok_virais": [...],
     "instagram_virais": [...], "youtube_virais": [...]}
    """
    client = anthropic.Anthropic()

    pedido = {
        "nicho": config["nome"],
        "perfil": config["perfil"],
        "pilares": config["pilares"],
        "restricoes": config["restricoes"],
        "quantidade_de_ideias": config["geracao"]["ideias_por_semana"],
        "duracao_alvo_segundos": config["geracao"]["duracao_alvo_segundos"],
        "sinais_de_tendencia_coletados": sinais,
    }

    messages = [
        {
            "role": "user",
            "content": (
                "Analise os sinais de tendência abaixo e gere as ideias com "
                "roteiros, seguindo exatamente o formato JSON combinado. Antes "
                "de escrever, use a busca web para (1) verificar o que está em "
                "alta agora no TikTok e no Instagram Reels neste nicho e "
                "(2) encontrar as referências científicas reais de cada roteiro.\n\n"
                + json.dumps(pedido, ensure_ascii=False, indent=2)
            ),
        }
    ]

    # A busca web roda no servidor da Anthropic; com stop_reason "pause_turn"
    # o turno é retomado reenviando o conteúdo parcial.
    while True:
        with client.messages.stream(
            model=MODELO,
            max_tokens=64000,
            system=PROMPT_SISTEMA,
            thinking={"type": "adaptive"},
            tools=[
                {
                    "type": "web_search_20260209",
                    "name": "web_search",
                    "max_uses": 12,
                }
            ],
            messages=messages,
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
        break

    texto = "".join(b.text for b in response.content if b.type == "text")
    return _extrair_json(texto)
