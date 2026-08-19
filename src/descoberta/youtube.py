"""Descoberta de vídeos virais no nicho via YouTube Data API v3.

Busca Shorts recentes pelas palavras-chave do nicho, coleta métricas e
ranqueia por uma pontuação que combina velocidade de visualização,
taxa de engajamento e "outlier score" (o quanto o vídeo performou acima
da média histórica do próprio canal — o melhor indicador de viral real,
porque separa o vídeo que estourou do canal que já é simplesmente grande).
"""

import os
from datetime import datetime, timedelta, timezone

import requests

API_BASE = "https://www.googleapis.com/youtube/v3"


def _get(endpoint: str, params: dict) -> dict:
    params = {**params, "key": os.environ["YOUTUBE_API_KEY"]}
    resp = requests.get(f"{API_BASE}/{endpoint}", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


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
                "descricao": snippet.get("description", "")[:300],
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
    return resultado[: cfg["top_n"]]
