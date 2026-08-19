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

1. EMBASAMENTO DE VIRALIDADE: cada ideia deve ser justificada pelos dados
   reais dos vídeos virais fornecidos (formato, gancho, tema, métricas).
   Cite o vídeo de referência e a métrica que sustenta a aposta.
2. EMBASAMENTO CIENTÍFICO: toda afirmação clínica do roteiro deve ter
   referência (diretriz, consenso de sociedade médica ou estudo). Use a
   busca web para localizar e citar as fontes — priorize sociedades
   brasileiras (SBD, CFM) e revistas indexadas. Nunca invente referência.

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
      "formato": "ex.: talking head com legenda dinâmica, POV, duetável...",
      "gancho_3s": "a primeira frase/cena que segura a atenção",
      "roteiro": "roteiro completo, fala a fala, com indicação de cena/corte",
      "duracao_estimada_seg": 45,
      "embasamento_viral": "por que isso tende a performar, citando os dados dos virais analisados",
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


def gerar_roteiros(config: dict, virais: list[dict]) -> dict:
    """Gera as ideias/roteiros da semana a partir dos virais do nicho."""
    client = anthropic.Anthropic()

    pedido = {
        "nicho": config["nome"],
        "perfil": config["perfil"],
        "pilares": config["pilares"],
        "restricoes": config["restricoes"],
        "quantidade_de_ideias": config["geracao"]["ideias_por_semana"],
        "duracao_alvo_segundos": config["geracao"]["duracao_alvo_segundos"],
        "videos_virais_analisados": virais,
    }

    messages = [
        {
            "role": "user",
            "content": (
                "Analise os vídeos virais abaixo e gere as ideias com roteiros, "
                "seguindo exatamente o formato JSON combinado. Use a busca web "
                "para encontrar as referências científicas reais de cada roteiro.\n\n"
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
