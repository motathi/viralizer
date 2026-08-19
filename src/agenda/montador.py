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


def montar_agenda(config: dict, roteiros: dict, virais: list[dict]) -> str:
    """Gera o Markdown da agenda semanal a partir dos roteiros."""
    ideias = roteiros["ideias"]
    inicio = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 or 7)

    linhas = [
        f"# Agenda de Conteúdo — {config['nome']}",
        "",
        f"Semana de **{inicio.strftime('%d/%m/%Y')}** · "
        f"{len(ideias)} conteúdos · gerado com base em {len(virais)} vídeos virais do nicho",
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

    for i, ideia in enumerate(ideias, 1):
        dia, hora = SLOTS_SEMANA[(i - 1) % len(SLOTS_SEMANA)]
        linhas += [
            f"## {i}. {ideia['titulo']}",
            "",
            f"**{dia}, {hora}** · {ideia['pilar']} · ~{ideia['duracao_estimada_seg']}s · {ideia['formato']}",
            "",
            f"**🎣 Gancho (3 primeiros segundos):** {ideia['gancho_3s']}",
            "",
            "**🎬 Roteiro**",
            "",
            ideia["roteiro"],
            "",
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

    linhas += [
        "## Vídeos virais que embasaram esta agenda",
        "",
        "| Vídeo | Canal | Views | Engajamento | Outlier |",
        "|---|---|---|---|---|",
    ]
    for v in virais[:10]:
        linhas.append(
            f"| [{v['titulo'][:60]}]({v['url']}) | {v['canal']} | "
            f"{v['views']:,} | {v['taxa_engajamento']:.1%} | {v['outlier_score']}x |"
        )

    return "\n".join(linhas) + "\n"
