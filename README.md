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
| **TikTok — coleta local** | Vídeos virais das hashtags (PT/EN/ES) pelo seu navegador, **sem cota e sem custo** | `playwright` (instalado pelo painel) |
| TikTok/Instagram via Apify | Mesmos dados, mas de servidor — usado como reserva | `APIFY_API_TOKEN` (plano gratuito) |
| Busca web na análise | Confirma trends e localiza as referências científicas | já incluso |
| YouTube Shorts | Sinal complementar com "outlier score" | `YOUTUBE_API_KEY` (opcional) |
| TikTok Creative Center | Hashtags oficiais em alta | `playwright` (opcional; instável em CI) |

**Estratégia de coleta** (`--coleta`):

- `auto` (padrão): tenta a **coleta local gratuita** primeiro; se trouxer pouca coisa e houver token do Apify, usa o Apify como reserva
- `local`: só o navegador desta máquina — ilimitado e sem custo
- `apify`: só o serviço, útil em servidor

A coleta local funciona porque roda **pelo seu IP residencial**: o TikTok trata como navegação normal. Em servidores de datacenter (GitHub Actions) ela é bloqueada — por isso o Apify segue como reserva na nuvem. Volume baixo é essencial: uma coleta por semana em algumas hashtags é indistinguível de uso comum.

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

## Uso simples: painel com um clique

Para gerar a agenda sem mexer em terminal, use o painel local — ele roda **na sua
máquina, pelo seu IP**:

1. Dê um duplo clique no atalho da sua plataforma:
   - **Windows**: `abrir-painel.bat`
   - **Mac**: `abrir-painel.command`
   - **Linux**: `abrir-painel.sh`
2. O navegador abre em `http://127.0.0.1:8777` (só acessível neste computador)
3. Clique em **🧪 Testar coleta (grátis)** para conferir se a busca de virais funciona aí — não gasta nada
4. Clique em **▶ Gerar agenda desta semana** e acompanhe o progresso ao vivo
5. Ao terminar, use **👀 Abrir agenda** para ver o resultado e **☁️ Publicar no site**
   para enviar ao GitHub (a Vercel publica em ~1 minuto)

O painel instala sozinho o que falta e traduz os erros técnicos para linguagem
simples (créditos acabando, chave faltando, sem internet).

## Uso pelo terminal

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

O painel local fica em `src/painel/` e não precisa de nenhuma dependência extra.

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

- TikTok e Instagram não têm API pública de tendências. A coleta local resolve isso rodando pelo seu IP, mas depende do seu computador estar ligado; na nuvem, o Apify (com cota mensal) é a reserva.
- Coletar dados públicos contraria os termos de uso das plataformas. Em volume baixo e sem login, o risco prático é um bloqueio temporário do IP. Não faça login na coleta.
- O TikTok Creative Center saiu do fluxo — nunca funcionou de forma confiável e a coleta local o substitui com vantagem.
- O conteúdo gerado é um **rascunho embasado**: a revisão final de qualquer afirmação médica é sempre da profissional.
