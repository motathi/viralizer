"""Montagem da agenda semanal de conteúdo em Markdown."""

from datetime import date, timedelta

# Janelas com bom desempenho médio para conteúdo de saúde/estética no Brasil.
# São ponto de partida — o desempenho real do perfil deve recalibrar isso.
SLOTS_SEMANA = [
    ("Segunda-feira", "18h30"),
    ("Terça-feira", "12h00"),
    ("Quarta-feira", "19h00"),
    ("Quinta-feira", "12h00"),
    ("Sexta-feira", "17h30"),
    ("Sábado", "10h00"),
    ("Domingo", "20h00"),
]


def normalizar_ideia(ideia: dict) -> dict:
    """Aceita tanto o esquema novo (ganchos_3s, roteiro_reels, carrossel)
    quanto o antigo (gancho_3s, roteiro em texto), devolvendo o novo."""
    n = dict(ideia)
    if "ganchos_3s" not in n:
        n["ganchos_3s"] = [n.get("gancho_3s", "")]
    if "roteiro_reels" not in n:
        n["roteiro_reels"] = [
            {"tempo": "", "fala": n.get("roteiro", ""), "direcao": ""}
        ]
    n.setdefault("roteiro_carrossel", {"capa": "", "laminas": [], "cta_final": ""})
    n.setdefault("legenda_post", "")
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
        "| Dia | Horário | Conteúdo | Pilar | Formato |",
        "|---|---|---|---|---|",
    ]

    for i, ideia in enumerate(ideias):
        dia, hora = SLOTS_SEMANA[i % len(SLOTS_SEMANA)]
        linhas.append(
            f"| {dia} | {hora} | {ideia['titulo']} | {ideia['pilar']} | {ideia['formato']} |"
        )

    linhas += ["", "---", ""]

    for i, bruta in enumerate(ideias, 1):
        ideia = normalizar_ideia(bruta)
        dia, hora = SLOTS_SEMANA[(i - 1) % len(SLOTS_SEMANA)]
        origem = ideia.get("plataforma_origem_da_tendencia", "")
        carrossel = ideia["roteiro_carrossel"]
        linhas += [
            f"## {i}. {ideia['titulo']}",
            "",
            f"**{dia}, {hora}** · {ideia['pilar']} · ~{ideia['duracao_estimada_seg']}s · "
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
            f"**📈 Por que deve performar:** {ideia['embasamento_viral']}",
            "",
            "**🔬 Embasamento científico**",
            "",
            *[f"- {ref}" for ref in ideia["embasamento_cientifico"]],
            "",
            f"**⚖️ Conformidade CFM:** {ideia['conformidade_cfm']}",
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
