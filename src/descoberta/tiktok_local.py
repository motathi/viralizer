"""Coleta gratuita de virais do TikTok, direto da sua máquina.

Abre um navegador real (Playwright), navega nas páginas públicas das
hashtags do nicho como um visitante comum e intercepta as respostas que a
própria página consome. Sem chave, sem cota e sem custo.

Roda no SEU IP: por isso funciona no computador de casa e falha em
servidores de datacenter (GitHub Actions), onde o TikTok bloqueia. Volume
baixo é essencial — uma coleta por semana em algumas hashtags é
indistinguível de navegação normal.

Requer: pip install playwright && playwright install chromium
"""

import random
import time

# Respostas internas do TikTok que carregam listas de vídeos
ROTAS_COM_VIDEOS = ("/api/challenge/item_list", "/api/search/", "/api/post/item_list",
                    "/api/recommend/item_list", "/api/explore/item_list")


def _extrair_videos(payload: dict) -> list[dict]:
    """Converte a resposta bruta do TikTok em vídeos com métricas."""
    videos = []
    for item in payload.get("itemList") or []:
        stats = item.get("stats") or item.get("statsV2") or {}
        autor = (item.get("author") or {}).get("uniqueId", "")
        try:
            views = int(stats.get("playCount") or 0)
            likes = int(stats.get("diggCount") or 0)
            comentarios = int(stats.get("commentCount") or 0)
            compartilhamentos = int(stats.get("shareCount") or 0)
        except (TypeError, ValueError):
            continue
        if not views or not item.get("id"):
            continue
        videos.append({
            "fonte": "tiktok",
            "url": f"https://www.tiktok.com/@{autor}/video/{item['id']}",
            "descricao": (item.get("desc") or "")[:300],
            "autor": autor,
            "views": views,
            "likes": likes,
            "comentarios": comentarios,
            "compartilhamentos": compartilhamentos,
            "taxa_engajamento": round(
                (likes + comentarios + compartilhamentos) / views, 4),
        })
    return videos


def _rolar_pagina(pagina, vezes: int = 3) -> None:
    """Rola devagar, como uma pessoa, para carregar mais vídeos."""
    for _ in range(vezes):
        pagina.mouse.wheel(0, random.randint(1800, 2600))
        pagina.wait_for_timeout(random.randint(1200, 2200))


def virais_tiktok_local(config: dict, por_hashtag: int = 20) -> list[dict]:
    """Vídeos virais das hashtags do nicho, coletados pelo navegador local."""
    hashtags = config.get("hashtags_monitoradas", [])
    if not hashtags:
        return []
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("   (TikTok local: instale com 'pip install playwright' e "
              "'playwright install chromium')")
        return []

    minimo = config.get("descoberta", {}).get("min_views_tiktok", 50000)
    coletados: dict[str, dict] = {}

    try:
        with sync_playwright() as p:
            navegador = p.chromium.launch(headless=True)
            contexto = navegador.new_context(
                locale="pt-BR",
                viewport={"width": 1280, "height": 900},
                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/126.0.0.0 Safari/537.36"),
            )
            pagina = contexto.new_page()

            def interceptar(resposta) -> None:
                if not any(r in resposta.url for r in ROTAS_COM_VIDEOS):
                    return
                try:
                    for video in _extrair_videos(resposta.json()):
                        coletados.setdefault(video["url"], video)
                except Exception:  # noqa: BLE001 - resposta não-JSON é esperada
                    pass

            pagina.on("response", interceptar)

            for hashtag in hashtags:
                antes = len(coletados)
                try:
                    pagina.goto(f"https://www.tiktok.com/tag/{hashtag.lstrip('#')}",
                                wait_until="domcontentloaded", timeout=45000)
                    pagina.wait_for_timeout(3500)
                    _rolar_pagina(pagina, vezes=2 + por_hashtag // 20)
                except Exception as e:  # noqa: BLE001
                    print(f"   (#{hashtag}: {type(e).__name__})")
                    continue
                print(f"   #{hashtag}: +{len(coletados) - antes} vídeos")
                time.sleep(random.uniform(2.0, 4.0))  # ritmo humano entre hashtags

            navegador.close()
    except Exception as e:  # noqa: BLE001
        if "Executable doesn't exist" in str(e) or "playwright install" in str(e):
            print("   ⚠️  O navegador da coleta ainda não foi instalado. Rode uma vez:")
            print("       python -m playwright install chromium")
        else:
            print(f"   (TikTok local indisponível: {type(e).__name__})")
        return []

    videos = [v for v in coletados.values() if v["views"] >= minimo]
    videos.sort(key=lambda v: v["views"] * (1 + 10 * v["taxa_engajamento"]), reverse=True)
    return videos[:60]
