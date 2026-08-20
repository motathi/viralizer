# Radar de Conteúdo Viral

Ferramenta que **estuda os vídeos virais de um nicho**, entende o que fez cada um viralizar e, a partir desses padrões, gera **ideias de Reels/TikTok com roteiros prontos** — publicando tudo numa **agenda semanal interativa**, automaticamente, toda segunda-feira.

O primeiro nicho configurado é **dermatologia estética**, mas tudo é parametrizado por arquivo: basta criar um novo YAML em `config/nichos/` para usar em outra área.

## Metodologia — os virais vêm primeiro

A ordem importa: as ideias **derivam** dos virais, nunca o contrário.

```
1. COLETA            2. ANÁLISE (Haiku)        3. ESCRITA (Opus)      4. PUBLICAÇÃO
virais reais    ──►  estuda cada viral    ──►  aplica o padrão   ──►  agenda interativa
de TikTok e          (tema, gancho,            vencedor ao             + arquivo da
Instagram, em        formato, por que          escrever os             semana + histórico
PT, EN e ES          viralizou) e deriva       roteiros finais         anti-repetição
                     as pautas com fonte
```

- **Rastreabilidade**: cada ideia mostra o(s) viral(is) de origem com link clicável, métricas e o padrão aplicado — dá para assistir ao vídeo que inspirou antes de gravar.
- **Filtro de viralidade em 3 camadas**: na coleta (mínimo de views/likes), no prompt e no código (pauta cuja melhor âncora não é viral de verdade é descartada antes da etapa cara).
- **Importação de virais**: tema que estourou em inglês/espanhol e ainda não tem versão forte em PT-BR é tratado como janela de oportunidade, com adaptação cultural (nunca tradução literal).
- **Memória anti-repetição**: temas e ganchos já publicados ficam em `dados/historico-<nicho>.json` e são proibidos nas semanas seguintes.
- **Liberdade editorial total**: os roteiros são escritos com ousadia (opinião firme, humor, provocação, discordar de trends), sem autocensura nem ressalvas defensivas. A decisão editorial é de quem publica — a profissional tem autonomia e revisa cada roteiro antes de gravar. Se quiser evitar algum assunto, basta listá-lo em `preferencias` no YAML do nicho.

## Fontes de tendência

| Fonte | O que traz | Requisito |
|---|---|---|
| TikTok — vídeos virais | Vídeos com métricas completas das hashtags do nicho (PT/EN/ES) | `APIFY_API_TOKEN` (plano gratuito) |
| Instagram — top posts | Posts e reels de melhor desempenho das hashtags | `APIFY_API_TOKEN` |
| Busca web na análise | Confirma trends e localiza as referências científicas | já incluso |
| YouTube Shorts | Sinal complementar com "outlier score" | `YOUTUBE_API_KEY` (opcional) |
| TikTok Creative Center | Hashtags oficiais em alta | `playwright` (opcional; instável em CI) |

Toda fonte é opcional e falha graciosamente — o pipeline roda com as que estiverem configuradas.

## Modelos e custo

Duas etapas para equilibrar qualidade e custo (~US$ 0,60–0,90 por geração semanal):

| Etapa | Modelo | Papel |
|---|---|---|
| Pesquisa e curadoria | Claude Haiku 4.5 | Analisa os virais e faz as buscas web (máx. 8) |
| Escrita dos roteiros | Claude Opus | Escreve os roteiros finais numa passada, sem busca |

## Instalação

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # e preencha as chaves
```

| Variável | Onde obter | Obrigatória? |
|---|---|---|
| `ANTHROPIC_API_KEY` | [Claude Console](https://console.anthropic.com/) | Sim |
| `APIFY_API_TOKEN` | [Apify Console](https://console.apify.com/) | Recomendada (virais de TikTok/Instagram) |
| `YOUTUBE_API_KEY` | [Google Cloud Console](https://console.cloud.google.com/apis/library/youtube.googleapis.com) | Opcional |

## Uso

```bash
# Pipeline completo: coleta -> análise -> roteiros -> agenda -> site
python -m src.main --nicho dermatologia-estetica --publicar-site

# Só a coleta de virais (não gasta tokens de IA)
python -m src.main --nicho dermatologia-estetica --apenas-descoberta

# Re-renderizar o site após mudar o design (custo zero, usa a última geração)
python -m src.publicar.rerender --nicho dermatologia-estetica
```

Saídas:

| Caminho | Conteúdo |
|---|---|
| `web/index.html` | Agenda da semana (site publicado na Vercel) |
| `web/semanas/<data>.html` | Agendas arquivadas, acessíveis pelo seletor no painel |
| `dados/<nicho>.json` | Última geração, usada pelo `rerender` |
| `dados/historico-<nicho>.json` | Memória anti-repetição |
| `saida/<nicho>/<data>/` | `sinais.json`, `roteiros.json` e `agenda.md` da execução |

## O site

- Cards compactos que expandem ao clicar, com chip de views do viral de origem e logo da plataforma
- Escolha entre 3 ganchos (troca a abertura do roteiro), alternância **Reels ⇄ Carrossel**
- Fila de produção: **+ Adicionar à lista** → **Marcar como feita** (a feita sai da fila e vai para "Feitas")
- **✕ descartar** ideia individualmente, com opção de restaurar
- Copiar roteiro pronto e link compartilhável de um roteiro só (`#rN`)
- Aviso automático se a agenda ficar mais de 8 dias sem atualizar (falha na automação)
- Estado salvo no navegador, por semana

## Automação

`.github/workflows/agenda-semanal.yml` roda toda segunda às 3h (Brasília), ou manualmente pela aba **Actions**. As chaves ficam nos *secrets* do repositório; o commit da agenda dispara o deploy na Vercel.

## Criando um novo nicho

Copie `config/nichos/dermatologia-estetica.yaml`, ajuste palavras-chave, hashtags monitoradas, pilares, tom de voz, limiares de viralidade e (se quiser) `preferencias`, e rode com `--nicho <nome-do-arquivo>`.

## Limitações conhecidas

- TikTok e Instagram não têm API pública de tendências: a coleta depende dos scrapers gerenciados do Apify (plano gratuito tem limite mensal de créditos).
- O TikTok Creative Center não captura dados de forma confiável em runners de CI.
- O conteúdo gerado é um **rascunho embasado**: a revisão final de qualquer afirmação médica é sempre da profissional.
