"""Coleta gratuita de virais do TikTok, direto da sua máquina.

Abre um navegador real, navega nas páginas públicas do nicho como um
visitante comum e lê os vídeos que a própria página carrega. Sem chave,
sem cota e sem custo.

Roda no SEU IP: por isso funciona no computador de casa e falha em
servidores de datacenter (GitHub Actions), onde o TikTok bloqueia.

Três detalhes fazem a diferença entre coletar e voltar de mãos vazias:

1. Janela visível. O Chromium "headless" é reconhecido pelo TikTok, que
   devolve uma página sem nenhum vídeo — nenhum erro, só vazio. Por isso
   o padrão aqui é abrir a janela de verdade (COLETA_HEADLESS=1 força o
   contrário, para automações sem tela).
2. Perfil salvo em disco. Cookies e a verificação "não sou robô"
   sobrevivem de uma semana para a outra: você resolve uma vez só.
3. Três fontes de leitura. Se a interceptação das chamadas internas não
   pegar nada, o vídeo ainda é lido do JSON embutido na página e, em
   último caso, dos próprios cards na tela.

Requer: pip install playwright && playwright install chromium
"""

import json
import os
import random
import re
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PERFIL = RAIZ / ".navegador-coleta"  # cookies e verificação ficam aqui

# Respostas internas do TikTok que carregam listas de vídeos
ROTAS_COM_VIDEOS = ("/api/challenge/item_list", "/api/search/", "/api/post/item_list",
                    "/api/recommend/item_list", "/api/explore/item_list",
                    "/api/music/item_list", "/api/related/item_list")

UA_RESERVA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# Sinais de que o TikTok pediu verificação em vez de mostrar os vídeos
MARCAS_BLOQUEIO = ("captcha", "verify", "security check", "verificação de segurança",
                   "log in to tiktok", "faça login")

MULTIPLICADORES = {"k": 1_000, "mil": 1_000, "m": 1_000_000, "mi": 1_000_000,
                   "b": 1_000_000_000, "bi": 1_000_000_000, "g": 1_000_000_000}


def _num(*valores) -> int:
    """Primeiro valor que vira um inteiro maior que zero (stats vem como texto)."""
    for v in valores:
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if n:
            return n
    return 0


def _numero_abreviado(texto: str) -> int:
    """'1.2M', '12,3 mil', '840' -> inteiro. Usado só na leitura dos cards."""
    if not texto:
        return 0
    t = texto.strip().lower().replace("\xa0", " ")
    m = re.match(r"^([\d.,]+)\s*([a-z]*)$", t)
    if not m:
        return 0
    numero, sufixo = m.groups()
    # 1.234 (milhar) vs 1.2M (decimal): com sufixo o ponto é decimal
    numero = numero.replace(",", ".") if sufixo else numero.replace(".", "").replace(",", "")
    try:
        valor = float(numero)
    except ValueError:
        return 0
    return int(valor * MULTIPLICADORES.get(sufixo, 1))


def _parece_video(d: dict) -> bool:
    return (isinstance(d, dict) and d.get("id")
            and isinstance(d.get("author"), (dict, str))
            and isinstance(d.get("stats") or d.get("statsV2"), dict))


def _itens_de(payload) -> list[dict]:
    """Procura vídeos em qualquer formato de resposta.

    O TikTok já mudou o formato várias vezes (itemList, item_list,
    data[].item...). Em vez de apostar em um caminho fixo, varre a
    estrutura inteira atrás de objetos que tenham cara de vídeo.
    """
    achados, pilha = [], [payload]
    while pilha:
        atual = pilha.pop()
        if isinstance(atual, dict):
            if _parece_video(atual):
                achados.append(atual)
            else:
                pilha.extend(atual.values())
        elif isinstance(atual, list):
            pilha.extend(atual)
    return achados


def _normalizar(item: dict) -> dict | None:
    """Converte o vídeo bruto do TikTok no formato usado pelo resto do projeto."""
    stats = item.get("stats") or {}
    sv2 = item.get("statsV2") or {}
    autor = item.get("author")
    autor = autor.get("uniqueId", "") if isinstance(autor, dict) else str(autor or "")

    views = _num(stats.get("playCount"), sv2.get("playCount"))
    if not views:
        return None
    likes = _num(stats.get("diggCount"), sv2.get("diggCount"))
    comentarios = _num(stats.get("commentCount"), sv2.get("commentCount"))
    compart = _num(stats.get("shareCount"), sv2.get("shareCount"))
    return {
        "fonte": "tiktok",
        "url": f"https://www.tiktok.com/@{autor}/video/{item['id']}",
        "descricao": (item.get("desc") or "")[:600],
        "autor": autor,
        "views": views,
        "likes": likes,
        "comentarios": comentarios,
        "compartilhamentos": compart,
        "taxa_engajamento": round((likes + comentarios + compart) / views, 4),
    }


# ── Leitura da página ────────────────────────────────────────────────────

JS_JSON_EMBUTIDO = """
() => {
  const saida = [];
  const el = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__');
  if (el && el.textContent) saida.push(el.textContent);
  for (const chave of ['SIGI_STATE', '__NEXT_DATA__']) {
    if (window[chave]) { try { saida.push(JSON.stringify(window[chave])); } catch (e) {} }
  }
  return saida;
}
"""

JS_CARDS = """
() => {
  const vistos = new Set(), saida = [];
  document.querySelectorAll('a[href*="/video/"]').forEach(a => {
    if (vistos.has(a.href)) return;
    vistos.add(a.href);
    const caixa = a.closest('[data-e2e$="-item"]') || a.parentElement?.parentElement;
    const v = caixa && caixa.querySelector('strong[data-e2e="video-views"]');
    saida.push({
      url: a.href,
      views: v ? v.textContent : '',
      descricao: (a.getAttribute('title') || (caixa ? caixa.innerText : '') || '').slice(0, 600)
    });
  });
  return saida;
}
"""


def _do_json_embutido(pagina) -> list[dict]:
    """Vídeos que o TikTok entrega dentro do HTML, sem nenhuma chamada extra."""
    videos = []
    try:
        for bruto in pagina.evaluate(JS_JSON_EMBUTIDO) or []:
            try:
                dados = json.loads(bruto)
            except (ValueError, TypeError):
                continue
            for item in _itens_de(dados):
                v = _normalizar(item)
                if v:
                    videos.append(v)
    except Exception:  # noqa: BLE001 - página pode ter sido trocada no meio
        pass
    return videos


def _dos_cards(pagina) -> list[dict]:
    """Último recurso: lê o que está desenhado na tela (só views, sem engajamento)."""
    videos = []
    try:
        for card in pagina.evaluate(JS_CARDS) or []:
            views = _numero_abreviado(card.get("views", ""))
            url = (card.get("url") or "").split("?")[0]
            if not views or "/video/" not in url:
                continue
            autor = url.split("/@")[-1].split("/")[0] if "/@" in url else ""
            videos.append({
                "fonte": "tiktok", "url": url, "autor": autor,
                "descricao": (card.get("descricao") or "").strip()[:600],
                "views": views, "likes": 0, "comentarios": 0,
                "compartilhamentos": 0, "taxa_engajamento": 0.0, "parcial": True,
            })
    except Exception:  # noqa: BLE001
        pass
    return videos


def _contar_cards(pagina) -> int:
    """Quantos vídeos estão desenhados na tela agora."""
    try:
        return pagina.evaluate(
            "() => document.querySelectorAll('a[href*=\"/video/\"]').length") or 0
    except Exception:  # noqa: BLE001
        return 0


def _bloqueado(pagina) -> bool:
    """A página pediu captcha/login em vez de mostrar vídeos?"""
    try:
        alvo = f"{pagina.url} {pagina.title()}".lower()
    except Exception:  # noqa: BLE001
        return False
    return any(m in alvo for m in MARCAS_BLOQUEIO)


def _aguardar_liberacao(pagina, segundos: int = 120) -> bool:
    """Dá tempo de a pessoa resolver a verificação na janela aberta."""
    print("   ⏳ O TikTok pediu verificação. Resolva na janela do navegador que "
          f"abriu — aguardo até {segundos}s. (Você só faz isso uma vez.)")
    limite = time.time() + segundos
    while time.time() < limite:
        pagina.wait_for_timeout(3000)
        if not _bloqueado(pagina):
            print("   ✅ Verificação resolvida, seguindo a coleta.")
            return True
    print("   ⚠️  Continuo sem a verificação — esta página pode vir vazia.")
    return False


def _aceitar_cookies(pagina) -> None:
    for texto in ("Aceitar todos", "Allow all", "Accept all", "Aceitar tudo"):
        try:
            botao = pagina.get_by_role("button", name=texto)
            if botao.count():
                botao.first.click(timeout=2500)
                pagina.wait_for_timeout(800)
                return
        except Exception:  # noqa: BLE001
            continue


def _estabilizar(pagina) -> None:
    """Isola cada alvo do fracasso do anterior.

    Quando uma navegação falha, o Chrome ainda está a caminho da própria
    página de erro. Começar a próxima em cima disso interrompe as duas —
    um alvo que falha derruba todos os seguintes em cascata. Parar em
    about:blank antes de seguir corta essa corrente.
    """
    try:
        pagina.wait_for_timeout(800)
        pagina.goto("about:blank", timeout=10000)
    except Exception:  # noqa: BLE001
        pass


def _rolar_pagina(pagina, vezes: int = 3) -> None:
    """Rola devagar, como uma pessoa, para carregar mais vídeos."""
    for _ in range(vezes):
        pagina.mouse.wheel(0, random.randint(1800, 2600))
        pagina.wait_for_timeout(random.randint(1200, 2200))


def _alvos(config: dict) -> list[tuple[str, str, str]]:
    """Monta a lista de páginas a visitar: (rótulo, url, tipo).

    Três formas de busca, todas gratuitas:
    - hashtag: página da tag (#skincare)
    - palavra: busca por termo, pega vídeos sem hashtag ("protetor solar mito")
    - perfil: últimos vídeos de um perfil de referência do nicho
    """
    from urllib.parse import quote

    alvos = []
    for h in config.get("hashtags_monitoradas", []):
        tag = h.lstrip("#")
        alvos.append((f"#{tag}", f"https://www.tiktok.com/tag/{quote(tag)}", "hashtag"))
    for termo in config.get("buscas_por_palavra", []):
        alvos.append((f'"{termo}"',
                      f"https://www.tiktok.com/search/video?q={quote(termo)}", "palavra"))
    for perfil in config.get("perfis_referencia", []):
        u = perfil.lstrip("@")
        alvos.append((f"@{u}", f"https://www.tiktok.com/@{quote(u)}", "perfil"))
    return alvos


def _sem_tela() -> bool:
    """Servidor sem monitor (GitHub Actions, Linux sem X) — janela é impossível."""
    if os.environ.get("CI"):
        return True
    return os.name == "posix" and not os.environ.get("DISPLAY") and os.uname().sysname != "Darwin"


def _abrir_navegador(p, headless: bool):
    """Chrome/Edge de verdade primeiro; o Chromium do Playwright é a reserva.

    Navegador instalado na máquina levanta muito menos suspeita que o
    Chromium avulso — e o perfil salvo mantém a sessão entre semanas.
    """
    PERFIL.mkdir(parents=True, exist_ok=True)
    comum = dict(
        user_data_dir=str(PERFIL),
        headless=headless,
        args=["--disable-blink-features=AutomationControlled"],
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
        viewport={"width": 1280, "height": 900},
    )
    erro = None
    for canal in ("chrome", "msedge", None):
        try:
            if canal:
                return p.chromium.launch_persistent_context(channel=canal, **comum)
            return p.chromium.launch_persistent_context(user_agent=UA_RESERVA, **comum)
        except Exception as e:  # noqa: BLE001 - navegador ausente é esperado
            erro = e
    raise erro


def virais_tiktok_local(config: dict, por_hashtag: int = 20) -> list[dict]:
    """Vídeos virais do nicho por hashtag, palavra-chave e perfil de referência."""
    alvos = _alvos(config)
    if not alvos:
        return []
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("   (TikTok local: instale com 'pip install playwright' e "
              "'playwright install chromium')")
        return []

    headless = _sem_tela() or os.environ.get("COLETA_HEADLESS") == "1"
    if not headless:
        print("   Vou abrir uma janela do navegador — deixe ela aberta e não mexa. "
              "Se aparecer verificação, resolva que eu continuo sozinho.")

    minimo = config.get("descoberta", {}).get("min_views_tiktok", 50000)
    coletados: dict[str, dict] = {}
    respostas_vistas = 0
    houve_bloqueio = False
    amostras: list[str] = []  # o que o TikTok respondeu, quando não veio vídeo

    try:
        with sync_playwright() as p:
            contexto = _abrir_navegador(p, headless)
            contexto.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
            pagina = contexto.pages[0] if contexto.pages else contexto.new_page()

            def interceptar(resposta) -> None:
                nonlocal respostas_vistas
                if not any(r in resposta.url for r in ROTAS_COM_VIDEOS):
                    return
                respostas_vistas += 1
                rota = resposta.url.split("?")[0].replace("https://www.tiktok.com", "")
                try:
                    dados = resposta.json()
                except Exception as e:  # noqa: BLE001 - resposta não-JSON é esperada
                    if len(amostras) < 6:
                        amostras.append(f"{rota} [{resposta.status}] corpo ilegível "
                                        f"({type(e).__name__})")
                    return
                achados = [v for v in (_normalizar(i) for i in _itens_de(dados)) if v]
                for v in achados:
                    coletados.setdefault(v["url"], v)
                if not achados and len(amostras) < 6:
                    campos = (", ".join(list(dados)[:6]) if isinstance(dados, dict)
                              else type(dados).__name__)
                    amostras.append(f"{rota} [{resposta.status}] sem vídeo — campos: {campos}")

            pagina.on("response", interceptar)

            # Aquecimento: a primeira página costuma vir vazia porque a sessão
            # ainda não foi estabelecida. Passar pela home antes evita perder
            # os dois primeiros alvos da lista.
            try:
                pagina.goto("https://www.tiktok.com/", wait_until="domcontentloaded",
                            timeout=45000)
                pagina.wait_for_timeout(3000)
                _aceitar_cookies(pagina)
                if _bloqueado(pagina) and not headless:
                    houve_bloqueio = True
                    _aguardar_liberacao(pagina)
            except Exception:  # noqa: BLE001 - seguir mesmo sem o aquecimento
                _estabilizar(pagina)

            for rotulo, url, tipo in alvos:
                antes = len(coletados)
                try:
                    pagina.goto(url, wait_until="domcontentloaded", timeout=45000)
                    pagina.wait_for_timeout(3500)
                    if _bloqueado(pagina):
                        houve_bloqueio = True
                        if not headless:
                            _aguardar_liberacao(pagina)
                            pagina.goto(url, wait_until="domcontentloaded", timeout=45000)
                            pagina.wait_for_timeout(3000)
                    _rolar_pagina(pagina, vezes=2 + por_hashtag // 20)
                except Exception as e:  # noqa: BLE001
                    print(f"   ({rotulo}: {type(e).__name__}: "
                          f"{str(e).splitlines()[0][:120]})")
                    _estabilizar(pagina)
                    continue

                for v in _do_json_embutido(pagina):
                    coletados.setdefault(v["url"], v)
                if len(coletados) == antes:  # nada pelas duas vias: lê a tela
                    for v in _dos_cards(pagina):
                        coletados.setdefault(v["url"], v)

                for v in coletados.values():
                    v.setdefault("origem_busca", tipo)
                novos = len(coletados) - antes
                # sem vídeo, o número de cards na tela diz se a página veio vazia
                # (bloqueio) ou se veio cheia e a leitura é que falhou
                extra = "" if novos else f" — {_contar_cards(pagina)} na tela"
                print(f"   {rotulo} ({tipo}): +{novos} vídeos{extra}")
                time.sleep(random.uniform(2.0, 4.0))  # ritmo humano entre páginas

            contexto.close()
    except Exception as e:  # noqa: BLE001
        if "Executable doesn't exist" in str(e) or "playwright install" in str(e):
            print("   ⚠️  O navegador da coleta ainda não foi instalado. Rode uma vez:")
            print("       python -m playwright install chromium")
        else:
            # só a primeira linha: o Playwright anexa páginas de log do navegador
            print(f"   (TikTok local indisponível: {type(e).__name__}: "
                  f"{str(e).splitlines()[0]})")
        return []

    if not coletados:
        _explicar_vazio(respostas_vistas, houve_bloqueio, headless, amostras)
        return []

    videos = [v for v in coletados.values() if v["views"] >= minimo]
    if not videos:
        melhor = max(v["views"] for v in coletados.values())
        print(f"   ⚠️  {len(coletados)} vídeos encontrados, mas o mais visto tem "
              f"{melhor:,} views — abaixo do mínimo de {minimo:,}.".replace(",", "."))
        print("      Baixe 'min_views_tiktok' no arquivo do nicho se quiser aceitá-los.")
    videos.sort(key=lambda v: v["views"] * (1 + 10 * v["taxa_engajamento"]), reverse=True)
    # margem larga de propósito: quem afunila é a seleção por variedade
    # em src/roteiros/gerador.py, que precisa de material para escolher
    return videos[:150]


def _explicar_vazio(respostas: int, bloqueio: bool, headless: bool,
                    amostras: list[str] | None = None) -> None:
    """Zero vídeos tem causas diferentes — aponta a certa em vez de um erro genérico."""
    print("   ⚠️  O TikTok não devolveu nenhum vídeo.")
    if bloqueio:
        print("      Ele pediu verificação (captcha/login). Rode de novo com a janela "
              "visível e resolva uma vez — depois disso fica salvo.")
    elif headless:
        print("      A coleta rodou sem janela, e assim o TikTok costuma servir "
              "página vazia. Rode no seu computador, sem COLETA_HEADLESS=1.")
    elif respostas == 0:
        print("      A página abriu mas não carregou a lista de vídeos. Quase sempre "
              "é bloqueio por IP/região — tente de novo em alguns minutos, ou abra "
              "o tiktok.com no seu navegador normal e faça login uma vez.")
    else:
        print(f"      Recebi {respostas} respostas do TikTok, mas todas vieram sem vídeo.")
        print("      Isso acontece quando o navegador da coleta não tem uma sessão do")
        print("      TikTok. Faça login uma vez — é rápido e fica salvo:")
        print("          python -m src.descoberta.tiktok_conta")
        print("      (ou o botão '🔑 Conectar TikTok' no painel)")
    if amostras:
        print("\n      Detalhe técnico do que o TikTok respondeu:")
        for a in amostras:
            print(f"        · {a}")
