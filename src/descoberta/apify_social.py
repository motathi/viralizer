"""Vídeos virais de TikTok e Instagram via Apify (fonte opcional, por chave).

O Apify (apify.com) mantém scrapers gerenciados de TikTok e Instagram — a
alternativa mais estável ao scraping caseiro, que quebra a cada mudança das
plataformas. Tem plano gratuito com créditos mensais. Para habilitar, defina
APIFY_API_TOKEN no .env.

Atores usados:
- clockworks/tiktok-scraper: vídeos por hashtag, com métricas completas
- apify/instagram-hashtag-scraper: top posts/reels por hashtag
"""

import os

import requests

API_BASE = "https://api.apify.com/v2/acts"
TIMEOUT = 300  # scrapers levam alguns minutos


def _rodar_ator(ator: str, entrada: dict) -> list[dict]:
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        return []
    resp = requests.post(
        f"{API_BASE}/{ator}/run-sync-get-dataset-items",
        params={"token": token},
        json=entrada,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def virais_tiktok(config: dict) -> list[dict]:
    """Vídeos recentes com melhores métricas nas hashtags do nicho (TikTok)."""
    hashtags = config.get("hashtags_monitoradas", [])
    if not hashtags or not os.environ.get("APIFY_API_TOKEN"):
        return []
    try:
        itens = _rodar_ator(
            "clockworks~tiktok-scraper",
            {"hashtags": hashtags, "resultsPerPage": 20},
        )
    except Exception as e:
        print(f"   (TikTok/Apify indisponível: {type(e).__name__}: {e})")
        return []

    videos = []
    for v in itens:
        views = v.get("playCount") or 0
        if not views:
            continue
        engajamento = ((v.get("diggCount") or 0) + (v.get("commentCount") or 0)
                       + (v.get("shareCount") or 0)) / views
        videos.append(
            {
                "fonte": "tiktok",
                "url": v.get("webVideoUrl"),
                "descricao": (v.get("text") or "")[:300],
                "autor": (v.get("authorMeta") or {}).get("name"),
                "views": views,
                "likes": v.get("diggCount"),
                "comentarios": v.get("commentCount"),
                "compartilhamentos": v.get("shareCount"),
                "taxa_engajamento": round(engajamento, 4),
            }
        )
    minimo = config.get("descoberta", {}).get("min_views_tiktok", 50000)
    videos = [v for v in videos if v["views"] >= minimo]
    videos.sort(key=lambda x: x["views"] * (1 + 10 * x["taxa_engajamento"]), reverse=True)
    return videos[:20]


def virais_instagram(config: dict) -> list[dict]:
    """Top posts/reels das hashtags do nicho (Instagram)."""
    hashtags = config.get("hashtags_monitoradas", [])
    if not hashtags or not os.environ.get("APIFY_API_TOKEN"):
        return []
    try:
        itens = _rodar_ator(
            "apify~instagram-hashtag-scraper",
            {"hashtags": [h.lstrip("#") for h in hashtags], "resultsLimit": 20},
        )
    except Exception as e:
        print(f"   (Instagram/Apify indisponível: {type(e).__name__}: {e})")
        return []

    posts = []
    for p in itens:
        if p.get("type") not in (None, "Video", "Sidecar", "Image"):
            continue
        posts.append(
            {
                "fonte": "instagram",
                "url": p.get("url"),
                "descricao": (p.get("caption") or "")[:300],
                "autor": p.get("ownerUsername"),
                "views": p.get("videoViewCount"),
                "likes": p.get("likesCount"),
                "comentarios": p.get("commentsCount"),
                "eh_video": p.get("type") == "Video",
            }
        )
    minimo = config.get("descoberta", {}).get("min_likes_instagram", 2000)
    posts = [p for p in posts
             if (p.get("views") or 0) >= 10 * minimo or (p.get("likes") or 0) >= minimo]
    posts.sort(key=lambda x: (x.get("views") or x.get("likes") or 0), reverse=True)
    return posts[:20]
