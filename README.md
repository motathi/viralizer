# Radar de Conteúdo Viral

Ferramenta que pesquisa **vídeos virais** de um nicho nas redes sociais, gera **ideias de Reels/TikTok com roteiros completos e embasados**, e monta uma **agenda de conteúdo semanal**.

O primeiro nicho configurado é **dermatologia estética**, mas tudo é parametrizado por arquivo de configuração — basta criar um novo YAML em `config/nichos/` para usar em outra área.

## Como funciona

```
1. DESCOBERTA          2. ROTEIROS                    3. AGENDA
YouTube Data API  ──►  Claude (com busca web)    ──►  Agenda semanal
busca Shorts do        analisa os padrões virais      em Markdown, com
nicho, ranqueia por    e gera ideias + roteiros       dia, horário e
engajamento e          com embasamento científico     roteiro pronto
"outlier score"        e conformidade com o CFM
```

- **Embasamento duplo**: cada ideia vem justificada pelos **dados reais** dos vídeos virais encontrados (visualizações, engajamento, formato) e com **referências científicas** buscadas na web para as afirmações do roteiro.
- **Conformidade médica**: os roteiros gerados respeitam as regras de publicidade médica do CFM (Resolução CFM nº 2.336/2023) — sem promessa de resultado, sem sensacionalismo, antes/depois apenas nos termos permitidos.

## Instalação

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # e preencha as chaves
```

Você precisa de duas chaves no `.env`:

| Variável | Onde obter |
|---|---|
| `YOUTUBE_API_KEY` | [Google Cloud Console](https://console.cloud.google.com/apis/library/youtube.googleapis.com) — ative a YouTube Data API v3 (gratuita, 10.000 unidades/dia) |
| `ANTHROPIC_API_KEY` | [Claude Console](https://console.anthropic.com/) |

## Uso

```bash
# Pipeline completo: descoberta -> roteiros -> agenda
python -m src.main --nicho dermatologia-estetica

# Apenas descobrir os virais (sem gastar tokens de IA)
python -m src.main --nicho dermatologia-estetica --apenas-descoberta
```

A saída fica em `saida/<nicho>/<data>/`:

- `virais.json` — os vídeos virais encontrados, com métricas e pontuação
- `roteiros.json` — as ideias e roteiros gerados
- `agenda.md` — a agenda semanal pronta para entregar (este é o arquivo para a sua esposa 🙂)

Um exemplo do resultado final está em [`docs/exemplo-agenda.md`](docs/exemplo-agenda.md).

## Criando um novo nicho

Copie `config/nichos/dermatologia-estetica.yaml`, ajuste palavras-chave, pilares de conteúdo, tom de voz e restrições, e rode com `--nicho <nome-do-arquivo>`.

## Limitações conhecidas

- A descoberta usa a **YouTube Data API** (oficial e estável) como termômetro de virais — o que viraliza em Shorts espelha bem TikTok/Reels. TikTok e Instagram não têm API pública de busca de tendências; scrapers não-oficiais quebram com frequência e podem violar os termos de uso, então não são usados por padrão.
- O conteúdo gerado é um **rascunho embasado**: a revisão final de qualquer afirmação médica é sempre da profissional.
