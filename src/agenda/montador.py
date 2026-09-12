"""Montagem da agenda semanal de conteúdo em Markdown."""

from datetime import date, timedelta


def normalizar_ideia(ideia: dict) -> dict:
    """Aceita o esquema novo (ganchos_3s, roteiro_reels, roteiro_carrossel,
    legenda_post), o das agendas guardadas antes da renomeação (ganchos,
    reels, carrossel, legenda) e o mais antigo de todos (gancho_3s, roteiro
    em texto), devolvendo sempre o novo."""
    n = dict(ideia)
    # As agendas guardadas antes da renomeação têm os mesmos dados com outros
    # nomes. Sem isto elas caem nos defaults abaixo e a semana inteira aparece
    # no site sem gancho, sem roteiro e sem legenda — com o conteúdo intacto
    # no JSON, só invisível.
    for antigo, atual in (("ganchos", "ganchos_3s"), ("reels", "roteiro_reels"),
                          ("carrossel", "roteiro_carrossel"), ("legenda", "legenda_post")):
        if atual not in n and antigo in n:
            n[atual] = n[antigo]
    if "ganchos_3s" not in n:
        n["ganchos_3s"] = [n.get("gancho_3s", "")]
    if "roteiro_reels" not in n:
        n["roteiro_reels"] = [
            {"tempo": "", "fala": n.get("roteiro", ""), "direcao": ""}
        ]
    n.setdefault("roteiro_carrossel", {"capa": "", "laminas": [], "cta_final": ""})
    n.setdefault("legenda_post", "")
    n.setdefault("padrao_aplicado", "")
    n.setdefault("virais_origem", [])
    return n


def montar_agenda(config: dict, roteiros: dict, sinais: dict) -> str:
    """Gera o Markdown da agenda semanal a partir dos roteiros e sinais."""
    ideias = roteiros["ideias"]
    total_sinais = sum(len(v) for v in sinais.values())
    inicio = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 or 7)

    linhas = [
        f"# Agenda de Conteúdo — {config['nome']}",
        "",
        f"Semana de **{inicio.strftime('%d/%m/%Y')}** · "
        f"{len(ideias)} conteúdos · gerado com base em {total_sinais} sinais "
        "de tendência (TikTok, Instagram e YouTube)",
        "",
        "## Visão geral da semana",
        "",
        "| # | Conteúdo | Pilar | Formato |",
        "|---|---|---|---|",
    ]

    for i, ideia in enumerate(ideias, 1):
        linhas.append(
            f"| {i} | {ideia['titulo']} | {ideia['pilar']} | {ideia['formato']} |"
        )

    linhas += ["", "---", ""]

    for i, bruta in enumerate(ideias, 1):
        ideia = normalizar_ideia(bruta)
        origem = ideia.get("plataforma_origem_da_tendencia", "")
        carrossel = ideia["roteiro_carrossel"]
        linhas += [
            f"## {i}. {ideia['titulo']}",
            "",
            f"**{ideia['pilar']}** · ~{ideia['duracao_estimada_seg']}s · "
            f"{ideia['formato']}" + (f" · tendência vinda de: {origem}" if origem else ""),
            "",
            "**🎣 Opções de gancho (3 primeiros segundos)**",
            "",
            *[f"{n}. {g}" for n, g in enumerate(ideia["ganchos_3s"], 1)],
            "",
            "**🎬 Roteiro (Reels/TikTok)**",
            "",
            *[
                f"- **[{b.get('tempo', '')}]** {b.get('fala', '')}"
                + (f"\n  - 🎥 {b['direcao']}" if b.get("direcao") else "")
                for b in ideia["roteiro_reels"]
            ],
            "",
            *(
                [
                    "**🖼️ Versão carrossel**",
                    "",
                    f"- **Capa:** {carrossel.get('capa', '')}",
                    *[f"- Lâmina {n}: {l}" for n, l in enumerate(carrossel.get("laminas", []), 1)],
                    f"- **CTA final:** {carrossel.get('cta_final', '')}",
                    "",
                ]
                if carrossel.get("laminas")
                else []
            ),
            *(
                [f"**✍️ Legenda do post:** {ideia['legenda_post']}", ""]
                if ideia.get("legenda_post")
                else []
            ),
            *(
                [
                    "**🎯 Virais que inspiraram**",
                    "",
                    *[
                        f"- [{v.get('autor', 'vídeo')}]({v.get('url', '')}) — "
                        f"{v.get('metrica', '')} — {v.get('por_que_viralizou', '')}"
                        for v in ideia["virais_origem"]
                    ],
                    *(
                        [f"- **Padrão aplicado:** {ideia['padrao_aplicado']}"]
                        if ideia.get("padrao_aplicado") else []
                    ),
                    "",
                ]
                if ideia["virais_origem"]
                else []
            ),
            f"**📈 Por que deve performar:** {ideia['embasamento_viral']}",
            "",
            "**🔬 Embasamento científico**",
            "",
            *[f"- {ref}" for ref in ideia["embasamento_cientifico"]],
            "",
            *([f"**📝 Observação:** {ideia['conformidade_cfm']}"]
              if ideia.get("conformidade_cfm") else []),
            "",
            f"**📣 CTA:** {ideia['cta']}",
            "",
            f"**#️⃣ Hashtags:** {' '.join(ideia['hashtags'])}",
            "",
            "---",
            "",
        ]

    linhas += ["## Sinais de tendência que embasaram esta agenda", ""]

    rotulos = {
        "tiktok_creative_center": "TikTok — hashtags em alta (Creative Center)",
        "tiktok_virais": "TikTok — vídeos virais do nicho",
        "instagram_virais": "Instagram — top posts do nicho",
        "youtube_virais": "YouTube Shorts — vídeos virais do nicho",
    }
    for chave, itens in sinais.items():
        if not itens:
            continue
        linhas += [f"### {rotulos.get(chave, chave)}", ""]
        for item in itens[:8]:
            titulo = (item.get("titulo") or item.get("descricao")
                      or item.get("hashtag") or "?")
            metricas = " · ".join(
                f"{n}: {item[c]:,}" if isinstance(item.get(c), int) else f"{n}: {item[c]}"
                for c, n in (("views", "views"), ("likes", "likes"),
                             ("taxa_engajamento", "engaj."), ("outlier_score", "outlier"),
                             ("publicacoes", "posts"), ("rank", "rank"))
                if item.get(c) is not None
            )
            url = item.get("url")
            titulo_md = f"[{titulo[:70]}]({url})" if url else f"**{titulo[:70]}**"
            linhas.append(f"- {titulo_md} — {metricas}")
        linhas.append("")

    return "\n".join(linhas) + "\n"
