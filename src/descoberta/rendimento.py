"""O que cada termo de busca rendeu, e quais termos novos a coleta sugere.

Sem isto, escolher termo de busca é chute: você adiciona "pele", a coleta
roda, e nada diz se aquilo trouxe viral ou lixo. Aqui o próprio resultado
da semana responde — e propõe os termos que os virais do nicho estão
usando e que ainda não são monitorados.
"""

import re
from collections import Counter

# Palavras que aparecem em qualquer legenda e não distinguem assunto
VAZIAS = {
    "para", "como", "isso", "esse", "essa", "seus", "suas", "mais", "menos",
    "você", "voce", "vocês", "voces", "então", "entao", "porque", "quando",
    "sobre", "todos", "todas", "muito", "muita", "pode", "posso", "fazer",
    "aqui", "agora", "hoje", "dica", "dicas", "vídeo", "video", "gente",
    "quem", "isso", "meu", "minha", "tudo", "nada", "bem", "vai", "tem",
    "with", "this", "that", "your", "from", "have", "what", "when", "will",
    "about", "just", "like", "they", "them", "here", "there", "into",
    "pero", "esto", "esta", "todo", "toda", "muy", "para", "que",
    "fyp", "foryou", "foryoupage", "viral", "parati", "tiktok", "trend",
}


def _monitorados(config: dict) -> set[str]:
    termos = set()
    for h in config.get("hashtags_monitoradas", []):
        termos.add(h.lstrip("#").lower())
    for termo in config.get("buscas_por_palavra", []):
        termos.update(p.lower() for p in termo.split())
    return termos


def _barra(n: int, maximo: int, largura: int = 22) -> str:
    if maximo <= 0:
        return ""
    return "█" * max(1, round(n / maximo * largura)) if n else ""


def rendimento_por_termo(videos: list[dict]) -> None:
    """Quantos virais cada termo de busca entregou, do melhor ao pior."""
    if not videos:
        return
    contagem = Counter(v.get("origem_termo", "?") for v in videos)
    maximo = max(contagem.values())
    print("\n   📊 O que cada termo rendeu (vídeos que passaram no filtro):")
    for termo, n in contagem.most_common():
        print(f"      {termo[:34]:<34} {n:>3}  {_barra(n, maximo)}")


def termos_improdutivos(videos: list[dict], config: dict) -> None:
    """Termos configurados que não entregaram nenhum viral nesta rodada."""
    produtivos = {v.get("origem_termo") for v in videos}
    ociosos = []
    for h in config.get("hashtags_monitoradas", []):
        if f"#{h.lstrip('#')}" not in produtivos:
            ociosos.append(f"#{h.lstrip('#')}")
    for termo in config.get("buscas_por_palavra", []):
        if f'"{termo}"' not in produtivos:
            ociosos.append(f'"{termo}"')
    if ociosos:
        print(f"\n   💤 Não trouxeram viral nenhum: {', '.join(ociosos)}")
        print("      Se repetir por várias semanas, troque no arquivo do nicho.")


def termos_sugeridos(videos: list[dict], config: dict, quantos: int = 8) -> list[str]:
    """Hashtags e palavras que os virais usam e que você ainda não monitora."""
    ja = _monitorados(config)
    tags: Counter = Counter()
    palavras: Counter = Counter()
    for v in videos:
        texto = (v.get("descricao") or "").lower()
        for tag in re.findall(r"#([a-zà-ú0-9_]{4,})", texto):
            if tag not in ja and tag not in VAZIAS:
                tags[tag] += 1
        for palavra in re.findall(r"(?<!#)\b[a-zà-ú]{5,}\b", texto):
            if palavra not in ja and palavra not in VAZIAS:
                palavras[palavra] += 1

    # só vale sugerir o que aparece em vários virais, não em um só
    sugestoes = [f"#{t}" for t, n in tags.most_common(quantos) if n >= 3]
    sugestoes += [p for p, n in palavras.most_common(quantos) if n >= 4]
    if sugestoes:
        print(f"\n   💡 Termos que os virais desta semana usam e você não monitora:")
        print(f"      {', '.join(sugestoes[:quantos])}")
        print("      Vale testar um ou dois em 'buscas_por_palavra' ou "
              "'hashtags_monitoradas'.")
    return sugestoes[:quantos]


def relatorio(videos: list[dict], config: dict) -> list[str]:
    """Imprime os três relatórios e devolve os termos sugeridos, para o histórico."""
    rendimento_por_termo(videos)
    termos_improdutivos(videos, config)
    return termos_sugeridos(videos, config)
