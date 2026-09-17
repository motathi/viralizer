"""Descoberta de vídeos virais no nicho via YouTube Data API v3.

Busca Shorts recentes pelas palavras-chave do nicho, coleta métricas e
ranqueia por uma pontuação que combina velocidade de visualização,
taxa de engajamento e "outlier score" (o quanto o vídeo performou acima
da média histórica do próprio canal — o melhor indicador de viral real,
porque separa o vídeo que estourou do canal que já é simplesmente grande).

Dos que passam, baixa a TRANSCRIÇÃO — o que é falado dentro do vídeo. É ela
que importa: título e descrição são texto de vitrine, escritos para o
algoritmo, e não dizem como a pessoa fala nem o que ela de fato diz. O
objetivo da ferramenta é compreender o vídeo, e isso mora na fala.
"""

import os
import re
from datetime import datetime, timedelta, timezone

import requests

API_BASE = "https://www.googleapis.com/youtube/v3"

# A transcrição é a evidência principal, então cabe bem mais que os 600
# caracteres da descrição. Um Short de 60s dá umas 1.500 letras de fala.
MAX_TRANSCRICAO = 4000

# Ordem de preferência: a legenda no idioma do nicho primeiro, depois as
# outras duas línguas que dominam o conteúdo de dermatologia.
IDIOMAS_PADRAO = ("pt", "pt-BR", "en", "es")


def _limpar_fala(texto: str) -> str:
    """Tira as marcações de legenda automática, que não são fala."""
    texto = re.sub(r"\[[^\]]{0,40}\]", " ", texto)     # [Música], [Aplausos]
    texto = re.sub(r"\([^)]{0,40}\)", " ", texto)       # (risos)
    return re.sub(r"\s+", " ", texto).strip()


def transcricao(video_id: str, idiomas: tuple[str, ...] = IDIOMAS_PADRAO) -> str:
    """A fala do vídeo, ou string vazia quando não há legenda disponível.

    Devolver vazio é resposta legítima: vídeo sem legenda existe, e nesse
    caso o sinal vale pelas métricas. Quem chama decide o que fazer.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return ""
    try:
        api = YouTubeTranscriptApi()
        if hasattr(api, "fetch"):                    # biblioteca 1.x
            falas = [t.text for t in api.fetch(video_id, languages=list(idiomas))]
        else:                                        # biblioteca 0.x
            falas = [t["text"] for t in
                     YouTubeTranscriptApi.get_transcript(video_id, languages=list(idiomas))]
    except Exception:
        # A biblioteca levanta uma família grande de exceções próprias
        # (sem legenda, legenda desativada, vídeo privado, bloqueio por IP).
        # Nenhuma delas justifica derrubar a coleta inteira.
        return ""
    return _limpar_fala(" ".join(falas))[:MAX_TRANSCRICAO]


def _get(endpoint: str, params: dict) -> dict:
    params = {**params, "key": os.environ["YOUTUBE_API_KEY"].strip()}
    resp = requests.get(f"{API_BASE}/{endpoint}", params=params, timeout=30)
    if not resp.ok:
        raise RuntimeError(_recado_do_erro(resp))
    return resp.json()


def _recado_do_erro(resp) -> str:
    """Traduz a recusa do Google para algo que diga o que fazer.

    Sem isto, um 403 vira um traceback de requests no meio da coleta e não
    diz se o problema é a chave, a API desligada ou a cota do dia.
    """
    try:
        erro = resp.json().get("error", {})
        motivo = (erro.get("errors") or [{}])[0].get("reason", "")
        detalhe = erro.get("message", "")
    except Exception:
        motivo, detalhe = "", resp.text[:200]
    recados = {
        "accessNotConfigured":
            "a YouTube Data API v3 não está ativada neste projeto do Google Cloud. "
            "Ative em console.cloud.google.com → APIs e serviços → Biblioteca.",
        "quotaExceeded":
            "a cota do dia acabou (são 10 mil unidades grátis, e cada busca custa 100). "
            "Volta a funcionar amanhã.",
        "dailyLimitExceeded": "o limite diário da chave foi atingido. Volta amanhã.",
        "keyInvalid": "a chave não é válida. Confira YOUTUBE_API_KEY no .env.",
        "ipRefererBlocked":
            "a chave tem restrição de uso (IP, site ou app) e este computador não passa. "
            "Tire a restrição ou libere este uso no Google Cloud.",
        "forbidden": "o Google recusou a chave. Confira se ela é de uma YouTube Data API v3.",
    }
    return recados.get(motivo, f"o Google respondeu {resp.status_code} ({motivo or 'sem motivo'}): {detalhe}"[:300])


def _buscar_ids(palavra_chave: str, dias_janela: int, max_resultados: int) -> list[str]:
    publicado_apos = (
        datetime.now(timezone.utc) - timedelta(days=dias_janela)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = _get(
        "search",
        {
            "part": "id",
            "q": palavra_chave,
            "type": "video",
            "videoDuration": "short",
            "order": "viewCount",
            "publishedAfter": publicado_apos,
            "maxResults": max_resultados,
            "relevanceLanguage": "pt",
        },
    )
    return [item["id"]["videoId"] for item in data.get("items", [])]


def _detalhes_videos(video_ids: list[str]) -> list[dict]:
    videos = []
    for i in range(0, len(video_ids), 50):  # limite de 50 ids por chamada
        data = _get(
            "videos",
            {"part": "snippet,statistics", "id": ",".join(video_ids[i : i + 50])},
        )
        videos.extend(data.get("items", []))
    return videos


def _media_views_canais(channel_ids: set[str]) -> dict[str, float]:
    medias = {}
    ids = list(channel_ids)
    for i in range(0, len(ids), 50):
        data = _get("channels", {"part": "statistics", "id": ",".join(ids[i : i + 50])})
        for canal in data.get("items", []):
            stats = canal["statistics"]
            n_videos = int(stats.get("videoCount", 0) or 0)
            total_views = int(stats.get("viewCount", 0) or 0)
            medias[canal["id"]] = total_views / n_videos if n_videos else 0.0
    return medias


def descobrir_virais(config: dict) -> list[dict]:
    """Retorna os top N vídeos virais do nicho, com métricas e pontuação."""
    cfg = config["descoberta"]

    ids: list[str] = []
    for palavra in config["palavras_chave"]:
        ids.extend(_buscar_ids(palavra, cfg["dias_janela"], cfg["max_por_palavra_chave"]))
    ids = list(dict.fromkeys(ids))  # remove duplicados preservando ordem
    print(f"      {len(ids)} vídeos encontrados em {len(config['palavras_chave'])} buscas "
          f"(últimos {cfg['dias_janela']} dias)")
    if not ids:
        print("      ⚠️  A busca não trouxe vídeo nenhum. Com palavras comuns do nicho "
              "isso é estranho — confira a janela de dias e as palavras_chave do nicho.")
        return []

    videos = _detalhes_videos(ids)
    medias_canal = _media_views_canais({v["snippet"]["channelId"] for v in videos})

    agora = datetime.now(timezone.utc)
    resultado = []
    for v in videos:
        stats = v.get("statistics", {})
        views = int(stats.get("viewCount", 0) or 0)
        likes = int(stats.get("likeCount", 0) or 0)
        comentarios = int(stats.get("commentCount", 0) or 0)
        if views == 0:
            continue

        snippet = v["snippet"]
        publicado = datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00"))
        dias_no_ar = max((agora - publicado).total_seconds() / 86400, 0.5)
        media_canal = medias_canal.get(snippet["channelId"], 0.0)

        engajamento = (likes + comentarios) / views
        views_por_dia = views / dias_no_ar
        outlier = views / media_canal if media_canal else 1.0

        resultado.append(
            {
                "video_id": v["id"],
                "url": f"https://www.youtube.com/watch?v={v['id']}",
                "titulo": snippet["title"],
                "descricao": snippet.get("description", "")[:600],
                "canal": snippet["channelTitle"],
                "publicado_em": snippet["publishedAt"],
                "views": views,
                "likes": likes,
                "comentarios": comentarios,
                "taxa_engajamento": round(engajamento, 4),
                "views_por_dia": round(views_por_dia),
                "outlier_score": round(outlier, 2),
                # pontuação final: viral de verdade cresce rápido, engaja e
                # performa acima do histórico do canal
                "pontuacao": round(
                    views_por_dia * (1 + 10 * engajamento) * min(outlier, 20), 1
                ),
            }
        )

    resultado.sort(key=lambda x: x["pontuacao"], reverse=True)
    melhores = resultado[: cfg["top_n"]]

    # Só dos que sobraram: baixar transcrição dos descartados é trabalho à toa.
    idiomas = tuple(cfg.get("idiomas_legenda") or IDIOMAS_PADRAO)
    com_fala = 0
    for v in melhores:
        v["transcricao"] = transcricao(v["video_id"], idiomas)
        if v["transcricao"]:
            com_fala += 1
    print(f"      transcrição: {com_fala} de {len(melhores)} vídeos tinham legenda")
    if melhores and not com_fala:
        print("      ⚠️  Nenhuma transcrição veio. Sem a fala, sobra só o texto de "
              "vitrine — confira se youtube-transcript-api está instalado.")
    return melhores
