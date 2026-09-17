# Viralizer

## Objetivo principal: compreender o vídeo

A ferramenta existe para entender **o conteúdo falado dentro do vídeo**. É disso
que saem as pautas e os roteiros.

A evidência que vale é a **transcrição** — o que a pessoa diz, palavra por
palavra. Título, descrição e legenda são texto de vitrine, escritos para o
algoritmo: dizem o assunto, mas não dizem *como* foi dito, que é justamente o
que faz um vídeo colar. Trabalhar só com legenda não serve de quase nada.

Consequências práticas, ao mexer em qualquer parte do código:

- Ao adicionar uma fonte nova, a pergunta é **como obter a transcrição** dela.
  Métricas e legenda sozinhas não fecham o requisito.
- `fala_literal` e `trechos_literais` são trechos copiados da transcrição.
  Nunca preencher com legenda — passar uma pela outra estraga o roteiro.
- Vídeo sem legenda disponível é caso legítimo: o sinal vale pelas métricas, e
  a ausência deve ficar explícita, não ser disfarçada com texto de vitrine.
- Não baixar transcrição de vídeo que já foi descartado no ranqueamento.

### Onde cada fonte está hoje

| Fonte | Transcrição |
|---|---|
| YouTube | ✅ `src/descoberta/youtube.py`, via `youtube-transcript-api` |
| TikTok (coleta local) | ❌ só legenda — alguns atores do Apify expõem o arquivo de legenda automática |
| Instagram (Apify) | ❌ só legenda |

## Como rodar

```
python -m src.main --nicho dermatologia-estetica --publicar-site
```

Roda no computador do usuário, lendo as chaves do arquivo `.env` na raiz
(`ANTHROPIC_API_KEY`, `APIFY_API_TOKEN`, `YOUTUBE_API_KEY`). O GitHub Actions e a
Vercel têm as suas próprias cópias das chaves e não alimentam a rodada local.

Para reconstruir as páginas sem gerar roteiros de novo:

```
python -m src.publicar.rerender --nicho <nicho>
```

## Convenções

- Código, comentários, mensagens de erro e commits em **português**.
- Mensagem de erro aponta a causa real e o que fazer. Quando houver mais de uma
  causa possível para o mesmo sintoma, distinguir as duas em vez de mandar o
  usuário procurar no lugar errado.
- Falha silenciosa é bug: quando um passo é pulado por falta de chave ou de
  dado, tem de aparecer no terminal.
