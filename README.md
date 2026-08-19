# Radar de Conteúdo Viral

Ferramenta que pesquisa **vídeos virais** de um nicho nas redes sociais, gera **ideias de Reels/TikTok com roteiros completos e embasados**, e monta uma **agenda de conteúdo semanal**.

O primeiro nicho configurado é **dermatologia estética**, mas tudo é parametrizado por arquivo de configuração — basta criar um novo YAML em `config/nichos/` para usar em outra área.

## Como funciona

```
1. DESCOBERTA (multi-fonte)      2. ROTEIROS                    3. AGENDA
TikTok Creative Center      ──►  Claude (com busca web)    ──►  Agenda semanal
TikTok virais (Apify)            verifica as trends atuais      em Markdown, com
Instagram top posts (Apify)      de TikTok/Reels na web,        dia, horário e
YouTube Shorts (API oficial)     analisa os sinais e gera       roteiro pronto
cada fonte é opcional e          roteiros com embasamento
falha graciosamente              científico e conformidade CFM
```

**Fontes de tendência** — como as trends nascem primeiro no TikTok e no Instagram, eles são as fontes principais:

| Fonte | O que traz | Requisito |
|---|---|---|
| TikTok Creative Center | Hashtags em alta publicadas pelo próprio TikTok | `pip install playwright && playwright install chromium` (sem chave) |
| TikTok — vídeos virais | Vídeos com métricas completas das hashtags do nicho | `APIFY_API_TOKEN` (Apify, tem plano grátis) |
| Instagram — top posts | Top posts/reels das hashtags do nicho | `APIFY_API_TOKEN` |
| YouTube Shorts | Vídeos virais do nicho com "outlier score" | `YOUTUBE_API_KEY` (grátis) |
| Busca web na geração | O Claude confere na hora o que está em alta no TikTok/Reels | já incluso |

Toda fonte é opcional: o pipeline roda com as que estiverem configuradas e informa o que pulou.

- **Embasamento duplo**: cada ideia vem justificada pelos **sinais reais de tendência** coletados (plataforma, métricas, formato) e com **referências científicas** buscadas na web para as afirmações do roteiro.
- **Conformidade médica**: os roteiros gerados respeitam as regras de publicidade médica do CFM (Resolução CFM nº 2.336/2023) — sem promessa de resultado, sem sensacionalismo, antes/depois apenas nos termos permitidos.

## Instalação

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # e preencha as chaves
```

Para habilitar o TikTok Creative Center (recomendado, sem chave):

```bash
pip install playwright && playwright install chromium
```

Chaves no `.env`:

| Variável | Onde obter | Obrigatória? |
|---|---|---|
| `ANTHROPIC_API_KEY` | [Claude Console](https://console.anthropic.com/) | Sim (gera os roteiros) |
| `APIFY_API_TOKEN` | [Apify Console](https://console.apify.com/) — plano gratuito com créditos mensais | Recomendada (virais de TikTok e Instagram) |
| `YOUTUBE_API_KEY` | [Google Cloud Console](https://console.cloud.google.com/apis/library/youtube.googleapis.com) — YouTube Data API v3, gratuita | Opcional |

## Uso

```bash
# Pipeline completo: descoberta -> roteiros -> agenda
python -m src.main --nicho dermatologia-estetica

# Apenas descobrir os virais (sem gastar tokens de IA)
python -m src.main --nicho dermatologia-estetica --apenas-descoberta
```

A saída fica em `saida/<nicho>/<data>/`:

- `sinais.json` — todos os sinais de tendência coletados (TikTok, Instagram, YouTube), com métricas
- `roteiros.json` — as ideias e roteiros gerados
- `agenda.md` — a agenda semanal pronta para entregar (este é o arquivo para a sua esposa 🙂)

Um exemplo do resultado final está em [`docs/exemplo-agenda.md`](docs/exemplo-agenda.md).

## Criando um novo nicho

Copie `config/nichos/dermatologia-estetica.yaml`, ajuste palavras-chave, pilares de conteúdo, tom de voz e restrições, e rode com `--nicho <nome-do-arquivo>`.

## Limitações conhecidas

- TikTok e Instagram não oferecem API pública de busca de tendências. As fontes usadas são as mais estáveis disponíveis: os **dados oficiais do TikTok Creative Center** (via navegador headless — pode quebrar se o TikTok mudar a página) e os **scrapers gerenciados do Apify** (mantidos profissionalmente, mas dependem de plano). A busca web do Claude na geração funciona sempre, como rede de segurança.
- O conteúdo gerado é um **rascunho embasado**: a revisão final de qualquer afirmação médica é sempre da profissional.
