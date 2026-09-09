"""Comparação grosseira de assunto entre textos curtos.

Usada onde precisamos saber se dois textos falam da mesma coisa sem chamar
a IA: seleção variada de sinais, detecção de semana monotema e fusão de
padrões no caderno de aprendizado.
"""

import re

# Palavras que aparecem em qualquer legenda e não distinguem assunto nenhum
PALAVRAS_VAZIAS = {
    "para", "como", "isso", "esse", "essa", "seus", "suas", "mais", "menos",
    "você", "voce", "vocês", "voces", "então", "entao", "porque", "quando",
    "sobre", "todos", "todas", "muito", "muita", "pode", "posso", "fazer",
    "aqui", "agora", "hoje", "dica", "dicas", "vídeo", "video", "gente",
    "with", "this", "that", "your", "from", "have", "what", "when", "will",
    "pero", "esto", "esta", "todo", "toda", "muy",
}


def tokens(texto: str, radical: int | None = None) -> set[str]:
    """Palavras significativas de um texto.

    Com `radical`, cada palavra é cortada nesse tamanho: "desmontado" e
    "desmontar" viram "desmo", "respondendo" e "resposta" viram "respo".
    Frase curta com flexão diferente deixa de parecer assunto diferente.
    """
    palavras = {p for p in re.findall(r"[a-zà-ú]{4,}", (texto or "").lower())
                if p not in PALAVRAS_VAZIAS}
    return {p[:radical] for p in palavras} if radical else palavras


def parecidos(a: set, b: set, limite: float) -> bool:
    """Jaccard acima do limite = mesmo assunto."""
    return bool(a and b) and len(a & b) / len(a | b) > limite
