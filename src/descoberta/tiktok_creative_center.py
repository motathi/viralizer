"""Tendências do TikTok Creative Center (dados oficiais publicados pelo TikTok).

O Creative Center (ads.tiktok.com/business/creativecenter) publica as hashtags
em alta por país e período — é a fonte pública mais direta do que está
viralizando no TikTok. A API interna exige headers assinados por JavaScript,
então usamos um navegador headless (Playwright) que carrega a página oficial
e intercepta as respostas JSON que ela mesma consome.

Fonte opcional: se o Playwright não estiver instalado ou a página mudar,
retorna lista vazia e o pipeline segue com as demais fontes.

Instalação: pip install playwright && playwright install chromium
"""

URL_HASHTAGS = (
    "https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en"
)


def tendencias_tiktok(config: dict) -> list[dict]:
    """Retorna hashtags em alta no TikTok, com métricas de publicações e views."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("   (TikTok Creative Center pulado: instale 'playwright' para habilitar)")
        return []

    capturas: list[dict] = []

    def intercepta(resp):
        if "creative_radar_api" in resp.url and "hashtag/list" in resp.url:
            try:
                corpo = resp.json()
                if corpo.get("code") == 0:
                    capturas.extend((corpo.get("data") or {}).get("list", []))
            except Exception:
                pass

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            pagina = browser.new_context(locale="pt-BR").new_page()
            pagina.on("response", intercepta)
            pagina.goto(URL_HASHTAGS, wait_until="domcontentloaded", timeout=60000)
            pagina.wait_for_timeout(8000)
            # carrega mais páginas de tendências, se o botão existir
            for _ in range(3):
                try:
                    pagina.get_by_text("View More", exact=False).first.click(timeout=4000)
                    pagina.wait_for_timeout(3000)
                except Exception:
                    break
            browser.close()
    except Exception as e:
        print(f"   (TikTok Creative Center indisponível: {type(e).__name__}: {e})")
        return []

    if not capturas:
        print("   (TikTok Creative Center: página carregou mas nenhuma tendência "
              "foi capturada — possível tela de consentimento ou mudança no site)")

    vistos, tendencias = set(), []
    for item in capturas:
        nome = item.get("hashtag_name")
        if not nome or nome in vistos:
            continue
        vistos.add(nome)
        tendencias.append(
            {
                "fonte": "tiktok_creative_center",
                "hashtag": nome,
                "rank": item.get("rank"),
                "publicacoes": item.get("publish_cnt"),
                "views": item.get("video_views"),
                "pais": item.get("country_info", {}).get("value"),
            }
        )
    tendencias.sort(key=lambda t: t.get("rank") or 999)
    return tendencias[:50]
