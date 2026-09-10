"""Estúdio: uma ideia sua vira três roteiros; você escolhe, refina, guarda.

Fluxo: formulário (formato, estilo, tom, tamanho) -> a IA escreve três
opções em ângulos distintos -> a pessoa escolhe uma -> refina conversando
-> salva. Tudo com o manual do nicho e as preferências dela, para o
estúdio ter a mesma inteligência da agenda semanal.

O que é salvo entra na agenda, junto com as ideias das semanas geradas —
não há mais galeria à parte. As funções de leitura e gravação continuam
aqui porque é este arquivo que o painel e a publicação usam.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

import yaml

from src import feedback as feedback_mod
from src.roteiros import manual as manual_mod
from src.roteiros.gerador import (LIBERDADE_EDITORIAL, MODELO_ESCRITA, REGRAS_SEM_SAL,
                                  _extrair_json)

RAIZ = Path(__file__).resolve().parent.parent.parent

FORMATOS = {"video": "🎬 Vídeo (Reels/TikTok)", "carrossel": "🖼️ Carrossel",
            "stories": "📱 Sequência de stories"}
ESTILOS = ["Educativo direto", "Mito vs verdade", "Resposta a comentário",
           "Bastidor / humanizado", "História de caso (sem expor paciente)",
           "Lista / ranking", "Polêmica com posicionamento", "Antes e depois explicado"]
TONS = ["Acolhedor", "Direto e firme", "Bem-humorado", "Indignado / opinativo",
        "Técnico acessível", "Confidente (amiga que conta)"]
TAMANHOS = {"video": ["30s", "45s", "60s", "90s"],
            "carrossel": ["5 lâminas", "7 lâminas", "10 lâminas"],
            "stories": ["3 stories", "5 stories", "7 stories"]}

PROMPT_OPCOES = """\
Você é um roteirista sênior de conteúdo para redes sociais em nichos de
saúde, escrevendo para o perfil descrito. A pessoa te dá UMA ideia e os
parâmetros: formato, estilo, tom e tamanho. Você devolve TRÊS opções de
roteiro em ângulos claramente diferentes entre si — se der para trocar os
títulos e ninguém notar, refaça. Todas obedecem ao estilo e ao tom pedidos;
o que muda é o ângulo, a estrutura e a jogada de abertura.

FORMATO define a estrutura dos blocos:
- video: blocos por tempo ("0-3s", "3-12s", ...) até a duração pedida. Cada
  bloco tem a fala (como se diz em voz alta) e a direção de gravação
  (enquadramento, corte, texto na tela). Gancho nos 3 primeiros segundos.
- carrossel: blocos são lâminas. "Capa" com gancho curto que cabe na
  imagem, depois "Lâmina 2".."Lâmina N" com UMA ideia por lâmina em texto
  curto, e a última "CTA". A direção é a sugestão visual da lâmina.
- stories: blocos são stories em sequência, "Story 1".."Story N". Cada um
  diz o que falar ou escrever na tela e a direção: sticker (enquete, caixa
  de pergunta, quiz, deslizante), corte de bastidor, texto grande, cara na
  câmera. O primeiro story tem que segurar quem passa o dedo; o último
  fecha com uma ação (responder, salvar, mandar mensagem).

MANUAL DO NICHO (se vier em "manual_do_nicho"): conhecimento acumulado de
virais deste nicho — estruturas comprovadas, vozes, aberturas, vocabulário.
Use-o. PREFERÊNCIAS (se vier em "preferencias_reveladas"): o que ela
costuma escolher e descartar; pese a favor do que ela escolhe.

{REGRAS_SEM_SAL}
{LIBERDADE_EDITORIAL}
Responda SOMENTE com JSON válido:
{{
  "opcoes": [
    {{
      "titulo": "nome curto da opção",
      "angulo": "em uma frase, o que diferencia esta opção das outras",
      "gancho": "a primeira frase / a capa / o primeiro story",
      "blocos": [{{"rotulo": "0-3s | Capa | Story 1", "texto": "...", "direcao": "..."}}],
      "legenda": "2 a 4 frases, primeira linha forte, sem hashtags",
      "hashtags": ["#..."],
      "por_que_funciona": "1 a 2 frases, citando o manual quando se aplicar"
    }}
  ]
}}
Exatamente 3 opções.
"""

PROMPT_REFINAR = """\
Você é o mesmo roteirista, agora refinando UM roteiro em conversa com a
pessoa que vai publicá-lo. Você recebe o roteiro atual, os parâmetros
(formato, estilo, tom, tamanho), o histórico da conversa e o pedido novo.

- Faça exatamente o que foi pedido. Não "melhore" o que não foi pedido.
- Mantenha formato, estilo e tom, a menos que o pedido mude isso.
- Se o pedido for ambíguo, escolha a interpretação mais provável e diga
  qual foi na resposta.
- Se o pedido for uma pergunta (e não uma mudança), responda e devolva o
  roteiro sem alteração.
- Mantenha a estrutura de blocos coerente com o formato.

{REGRAS_SEM_SAL}
{LIBERDADE_EDITORIAL}
Responda SOMENTE com JSON válido:
{{
  "resposta": "1 a 3 frases, na sua voz, dizendo o que mudou e por quê",
  "roteiro": {{"titulo": "...", "angulo": "...", "gancho": "...",
               "blocos": [{{"rotulo": "...", "texto": "...", "direcao": "..."}}],
               "legenda": "...", "hashtags": ["#..."], "por_que_funciona": "..."}}
}}
"""


# ── configuração e contexto ──────────────────────────────────────────────

def _nichos() -> list[str]:
    return sorted(p.stem for p in (RAIZ / "config" / "nichos").glob("*.yaml"))


def _config(nicho: str) -> dict:
    return yaml.safe_load((RAIZ / "config" / "nichos" / f"{nicho}.yaml")
                          .read_text(encoding="utf-8"))


def _contexto(nicho: str) -> dict:
    """O que a IA precisa saber além do pedido: perfil, manual, preferências."""
    config = _config(nicho)
    ctx = {"nicho": config["nome"], "perfil": config.get("perfil", {}),
           "preferencias_do_perfil": config.get("preferencias", [])}
    manual = manual_mod.carregar(RAIZ, nicho)
    if manual:
        ctx["manual_do_nicho"] = manual_mod.para_prompt(manual)
    prefs = feedback_mod.preferencias(RAIZ, nicho)
    if prefs:
        ctx["preferencias_reveladas"] = prefs
    return ctx


def _sistema(molde: str) -> str:
    return (molde.replace("{REGRAS_SEM_SAL}", REGRAS_SEM_SAL)
                 .replace("{LIBERDADE_EDITORIAL}", LIBERDADE_EDITORIAL)
                 .replace("{{", "{").replace("}}", "}"))


def _conversar(system: str, messages: list[dict], max_tokens: int = 16000) -> str:
    """Chamada em streaming (evita timeout em respostas longas), sem ferramentas."""
    import anthropic
    client = anthropic.Anthropic()
    with client.messages.stream(model=MODELO_ESCRITA, max_tokens=max_tokens, system=system,
                                messages=messages, thinking={"type": "adaptive"}) as stream:
        resposta = stream.get_final_message()
    if resposta.stop_reason == "refusal":
        raise RuntimeError("O modelo recusou a solicitação.")
    return "".join(b.text for b in resposta.content if b.type == "text")


def _limpar_roteiro(r: dict) -> dict:
    """Garante o esqueleto que as páginas esperam, sem confiar no JSON da IA."""
    return {
        "titulo": str(r.get("titulo", "")).strip(),
        "angulo": str(r.get("angulo", "")).strip(),
        "gancho": str(r.get("gancho", "")).strip(),
        "blocos": [{"rotulo": str(b.get("rotulo", "")), "texto": str(b.get("texto", "")),
                    "direcao": str(b.get("direcao", ""))}
                   for b in (r.get("blocos") or []) if isinstance(b, dict)],
        "legenda": str(r.get("legenda", "")).strip(),
        "hashtags": [str(h) for h in (r.get("hashtags") or [])][:12],
        "por_que_funciona": str(r.get("por_que_funciona", "")).strip(),
    }


# ── motor ────────────────────────────────────────────────────────────────

def gerar_opcoes(pedido: dict) -> list[dict]:
    nicho = pedido.get("nicho") or (_nichos() or [""])[0]
    if nicho not in _nichos():
        raise ValueError("nicho inválido")
    ideia = str(pedido.get("ideia", "")).strip()
    if len(ideia) < 5:
        raise ValueError("Escreva a ideia com um pouco mais de detalhe.")
    formato = pedido.get("formato") if pedido.get("formato") in FORMATOS else "video"
    conteudo = {
        **_contexto(nicho),
        "pedido": {
            "ideia": ideia, "formato": formato,
            "estilo": str(pedido.get("estilo", "")), "tom": str(pedido.get("tom", "")),
            "tamanho": str(pedido.get("tamanho", "")),
            "observacoes": str(pedido.get("observacoes", ""))[:800],
        },
    }
    texto = _conversar(_sistema(PROMPT_OPCOES),
                       [{"role": "user", "content": json.dumps(conteudo, ensure_ascii=False, indent=2)}])
    opcoes = [_limpar_roteiro(o) for o in _extrair_json(texto).get("opcoes", []) if isinstance(o, dict)]
    if not opcoes:
        raise RuntimeError("A IA não devolveu opções. Tente de novo.")
    return opcoes[:3]


def refinar(pedido: dict) -> dict:
    nicho = pedido.get("nicho") or (_nichos() or [""])[0]
    if nicho not in _nichos():
        raise ValueError("nicho inválido")
    mensagem = str(pedido.get("mensagem", "")).strip()
    if not mensagem:
        raise ValueError("Diga o que quer mudar.")
    roteiro = _limpar_roteiro(pedido.get("roteiro") or {})
    contexto = {**_contexto(nicho), "parametros": pedido.get("parametros", {}),
                "roteiro_atual": roteiro}

    messages = [{"role": "user", "content": "Contexto e roteiro atual:\n"
                 + json.dumps(contexto, ensure_ascii=False, indent=2)},
                {"role": "assistant", "content": "Entendido. O que você quer mudar?"}]
    for turno in (pedido.get("conversa") or [])[-12:]:  # últimos turnos bastam
        papel = "user" if turno.get("papel") == "usuario" else "assistant"
        texto = str(turno.get("texto", "")).strip()
        if texto and messages[-1]["role"] != papel:
            messages.append({"role": papel, "content": texto})
    if messages[-1]["role"] == "user":
        messages.append({"role": "assistant", "content": "Certo."})
    messages.append({"role": "user", "content": mensagem})

    dados = _extrair_json(_conversar(_sistema(PROMPT_REFINAR), messages))
    novo = _limpar_roteiro(dados.get("roteiro") or roteiro)
    return {"resposta": str(dados.get("resposta", "")).strip() or "Feito.", "roteiro": novo}


# ── galeria ──────────────────────────────────────────────────────────────

def _caminho_galeria(nicho: str) -> Path:
    return RAIZ / "dados" / f"galeria-{nicho}.json"


def galeria_carregar(nicho: str) -> list[dict]:
    arquivo = _caminho_galeria(nicho)
    if not arquivo.exists():
        return []
    try:
        return json.loads(arquivo.read_text(encoding="utf-8")).get("itens", [])
    except (ValueError, OSError):
        return []


def _galeria_gravar(nicho: str, itens: list[dict]) -> None:
    arquivo = _caminho_galeria(nicho)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps({"itens": itens}, ensure_ascii=False, indent=2),
                       encoding="utf-8")


def galeria_salvar(nicho: str, dados: dict) -> str:
    """Cria ou atualiza (pelo id) um item da galeria. Devolve o id."""
    itens = galeria_carregar(nicho)
    agora = datetime.now().isoformat(timespec="minutes")
    item_id = str(dados.get("id") or uuid.uuid4().hex[:10])
    novo = {
        "id": item_id, "atualizado_em": agora,
        "ideia": str(dados.get("ideia", ""))[:500],
        "formato": dados.get("formato") if dados.get("formato") in FORMATOS else "video",
        "estilo": str(dados.get("estilo", "")), "tom": str(dados.get("tom", "")),
        "tamanho": str(dados.get("tamanho", "")),
        "roteiro": _limpar_roteiro(dados.get("roteiro") or {}),
    }
    for i, existente in enumerate(itens):
        if existente.get("id") == item_id:
            novo["criado_em"] = existente.get("criado_em", agora)
            itens[i] = novo
            break
    else:
        novo["criado_em"] = agora
        itens.append(novo)
    _galeria_gravar(nicho, itens)
    return item_id


def galeria_apagar(nicho: str, item_id: str) -> bool:
    itens = galeria_carregar(nicho)
    restantes = [i for i in itens if i.get("id") != item_id]
    if len(restantes) == len(itens):
        return False
    _galeria_gravar(nicho, restantes)
    return True


# ── roteador (chamado pelo painel) ───────────────────────────────────────

def _param(consulta: str, nome: str) -> str:
    from urllib.parse import parse_qs
    return (parse_qs(consulta).get(nome) or [""])[0]


def tratar(h, metodo: str, caminho: str, consulta: str, corpo: bytes) -> bool:
    """Atende as rotas do estúdio e da galeria. False = não é nossa."""
    if metodo == "GET":
        if caminho == "/estudio":
            h._responder(PAGINA_ESTUDIO.encode("utf-8")); return True
        if caminho == "/galeria":  # a galeria virou parte da agenda
            h.send_response(302); h.send_header("Location", "/agenda")
            h.send_header("Content-Length", "0"); h.end_headers(); return True
        if caminho == "/estudio/menus":
            nichos = _nichos()
            publico = _config(nichos[0]).get("perfil", {}).get("publico", "") if nichos else ""
            h._json({"nichos": nichos, "formatos": FORMATOS, "estilos": ESTILOS,
                     "tons": TONS, "tamanhos": TAMANHOS, "publico": publico}); return True
        if caminho == "/galeria/itens":
            nicho = _param(consulta, "nicho") or (_nichos() or [""])[0]
            itens = galeria_carregar(nicho) if nicho in _nichos() else []
            itens.sort(key=lambda i: i.get("atualizado_em", ""), reverse=True)
            h._json({"nicho": nicho, "itens": itens}); return True
        return False

    if not caminho.startswith(("/estudio/", "/galeria/")):
        return False
    try:
        dados = json.loads(corpo.decode("utf-8", "ignore") or "{}")
    except ValueError:
        h._json({"ok": False, "erro": "pedido inválido"}); return True

    try:
        if caminho == "/estudio/gerar":
            h._json({"ok": True, "opcoes": gerar_opcoes(dados)})
        elif caminho == "/estudio/refinar":
            h._json({"ok": True, **refinar(dados)})
        elif caminho == "/galeria/salvar":
            nicho = dados.get("nicho") or (_nichos() or [""])[0]
            if nicho not in _nichos():
                raise ValueError("nicho inválido")
            h._json({"ok": True, "id": galeria_salvar(nicho, dados)})
        elif caminho == "/galeria/apagar":
            nicho = dados.get("nicho") or (_nichos() or [""])[0]
            h._json({"ok": galeria_apagar(nicho, str(dados.get("id", "")))})
        else:
            return False
    except ValueError as e:
        h._json({"ok": False, "erro": str(e)})
    except Exception as e:  # noqa: BLE001 - a página mostra o recado
        h._json({"ok": False, "erro": _traduzir_erro(e)})
    return True


def _traduzir_erro(e: Exception) -> str:
    texto = str(e)
    if "authentication" in texto.lower() or "api_key" in texto.lower():
        return "Falta a chave da Anthropic. Volte ao painel e cole a chave no aviso do topo."
    if "credit balance" in texto:
        return "Os créditos da Anthropic acabaram. Recarregue em console.anthropic.com."
    if "Resposta sem JSON" in texto:
        return "A IA respondeu fora do formato. Tente de novo."
    return f"{type(e).__name__}: {texto.splitlines()[0][:160]}"


# ── páginas ──────────────────────────────────────────────────────────────

ESTILO_COMUM = """
  :root { --grad: linear-gradient(45deg,#405DE6,#833AB4 30%,#C13584 50%,#E1306C 70%,#F77737);
          --tinta:#1c1b1f; --suave:#6f6b76; --borda:#eceaef; --fundo:#fff; --painel:#fbfafc;
          --rosa:#C13584; --ok:#1f9d63 }
  * { box-sizing:border-box; margin:0 }
  body { font-family:Inter,"Segoe UI",system-ui,sans-serif; background:var(--fundo); color:var(--tinta);
         line-height:1.55; padding:30px 18px 70px }
  .wrap { max-width:1040px; margin:0 auto }
  a.voltar { display:inline-block; color:var(--suave); text-decoration:none; font-size:.9rem; margin-bottom:16px }
  h1 { font-size:1.5rem; font-weight:800; letter-spacing:-.025em }
  h1 span { background:var(--grad); -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent }
  .sub { color:var(--suave); font-size:.9rem; margin:4px 0 24px }
  h2 { font-size:.75rem; font-weight:700; letter-spacing:.11em; text-transform:uppercase; color:var(--suave); margin:0 0 10px }
  .cartao { border:1px solid var(--borda); border-radius:16px; padding:18px; background:var(--fundo) }
  .chip { display:inline-block; font-size:.74rem; font-weight:600; padding:3px 10px; border-radius:999px;
          background:var(--painel); border:1px solid var(--borda); color:var(--suave); margin-right:4px }
  button, a.btn { font:inherit; font-size:.9rem; font-weight:700; padding:10px 18px; border-radius:999px;
                  border:1.5px solid var(--borda); background:var(--fundo); color:var(--tinta); cursor:pointer;
                  text-decoration:none; white-space:nowrap; transition:border-color .18s,color .18s }
  button:hover:not(:disabled), a.btn:hover { border-color:var(--rosa); color:var(--rosa) }
  button.principal { background:var(--grad); border-color:transparent; color:#fff }
  button.principal:hover:not(:disabled) { color:#fff; filter:brightness(1.07) }
  button:disabled { opacity:.45; cursor:not-allowed }
  button:focus-visible, a.btn:focus-visible, select:focus-visible, textarea:focus-visible, input:focus-visible {
    outline:2px solid var(--rosa); outline-offset:2px }
  select, textarea, input[type=text] { font:inherit; font-size:.92rem; padding:10px 14px; border-radius:12px;
    border:1.5px solid var(--borda); background:var(--painel); color:var(--tinta); width:100% }
  textarea { min-height:96px; resize:vertical }
  .bloco { padding:10px 0; border-bottom:1px dashed var(--borda) }
  .bloco:last-child { border-bottom:0 }
  .bloco .rotulo { font-size:.72rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:var(--rosa) }
  .bloco .texto { margin:3px 0 }
  .bloco .direcao { color:var(--suave); font-size:.84rem }
  .gancho { font-weight:600; margin-bottom:10px }
  .legenda { background:var(--painel); border-radius:12px; padding:12px 14px; font-size:.9rem; white-space:pre-wrap }
  .tags { color:var(--suave); font-size:.85rem; margin-top:6px }
  .erro { background:#fff0f0; border:1px solid #ffc9c9; color:#8a1c1c; border-radius:12px; padding:12px 16px; margin:12px 0 }
  .girando { display:inline-block; width:13px; height:13px; border:2px solid #e2dfe6; border-top-color:var(--rosa);
             border-radius:50%; animation:g .8s linear infinite; margin-right:8px; vertical-align:-1px }
  @keyframes g { to { transform:rotate(360deg) } }
  @media (prefers-reduced-motion:reduce) { .girando { animation:none } }
  [hidden] { display:none !important }
"""

PAGINA_ESTUDIO = """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Estúdio — Radar de Conteúdo Viral</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>__ESTILO__
  .etapas { display:flex; gap:8px; margin-bottom:22px; flex-wrap:wrap }
  .etapa { font-size:.78rem; font-weight:600; color:var(--suave); padding:6px 12px; border-radius:999px; border:1px solid var(--borda) }
  .etapa.ativa { color:#fff; background:var(--grad); border-color:transparent }
  .form { display:grid; grid-template-columns:1fr 1fr; gap:14px }
  .form .larga { grid-column:1 / -1 }
  label { display:block; font-size:.8rem; font-weight:600; color:var(--suave); margin-bottom:5px }
  .acoes { display:flex; gap:10px; margin-top:16px; flex-wrap:wrap; align-items:center }
  .opcoes { display:grid; grid-template-columns:repeat(3, 1fr); gap:14px }
  .opcao { display:flex; flex-direction:column }
  .opcao .chip { align-self:flex-start }
  .opcao h3 { font-size:1rem; margin:8px 0 4px }
  .opcao .angulo { color:var(--suave); font-size:.86rem; margin-bottom:10px }
  .opcao .previa { flex:1; max-height:340px; overflow:auto; padding-right:4px }
  .opcao .por-que { font-size:.82rem; color:var(--suave); margin:10px 0 }
  .editor { display:grid; grid-template-columns:1.2fr .8fr; gap:16px; align-items:start }
  .chat { display:flex; flex-direction:column; max-height:78vh }
  .mensagens { flex:1; overflow:auto; display:flex; flex-direction:column; gap:10px; padding:4px 2px 12px }
  .msg { max-width:92%; padding:10px 14px; border-radius:16px; font-size:.92rem; white-space:pre-wrap }
  .msg.eu { align-self:flex-end; background:var(--grad); color:#fff; border-bottom-right-radius:4px }
  .msg.ia { align-self:flex-start; background:var(--painel); border:1px solid var(--borda); border-bottom-left-radius:4px }
  .entrada { display:flex; gap:8px; border-top:1px solid var(--borda); padding-top:12px }
  .entrada input { flex:1 }
  .sugestoes { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:10px }
  .sugestoes button { font-size:.78rem; padding:6px 11px; font-weight:600 }
  .salvo { background:#eefaf3; border:1px solid #bfe8cf; color:#146a3f; border-radius:12px; padding:12px 16px; margin-top:12px }
  @media (max-width:820px) {
    .form, .opcoes, .editor { grid-template-columns:1fr }
    .opcao .previa { max-height:none }
    .chat { max-height:none }
  }
</style></head><body><div class="wrap">
  <a class="voltar" href="/">← painel</a>
  <h1>Estúdio <span>de roteiros</span></h1>
  <p class="sub">Sua ideia, três roteiros em ângulos diferentes, e uma conversa para deixar do seu jeito.</p>

  <div class="etapas">
    <span class="etapa ativa" id="et1">1 · Ideia e formato</span>
    <span class="etapa" id="et2">2 · Escolha uma opção</span>
    <span class="etapa" id="et3">3 · Ajuste e salve</span>
  </div>

  <section id="passo1" class="cartao">
    <div class="form">
      <div class="larga"><label for="ideia">Sua ideia</label>
        <textarea id="ideia" placeholder="Ex.: explicar por que protetor solar dentro de casa faz diferença, usando a luz da janela do consultório como prova"></textarea></div>
      <div><label for="formato">Formato</label><select id="formato"></select></div>
      <div><label for="tamanho">Tamanho</label><select id="tamanho"></select></div>
      <div><label for="estilo">Estilo</label><select id="estilo"></select></div>
      <div><label for="tom">Tom</label><select id="tom"></select></div>
      <div class="larga"><label for="obs">Observações (opcional)</label>
        <input type="text" id="obs" placeholder="Ex.: mencionar que atendo em Curitiba; não usar a palavra 'milagre'"></div>
      <div hidden><select id="nicho"></select></div>
    </div>
    <div class="acoes">
      <button class="principal" id="gerar">Escrever 3 opções</button>
      <span id="estado1"></span>
    </div>
    <div class="erro" id="erro1" hidden></div>
  </section>

  <section id="passo2" hidden>
    <h2>Três ângulos para a mesma ideia — escolha um</h2>
    <div class="opcoes" id="opcoes"></div>
    <div class="acoes"><button id="voltar1">← Mudar a ideia ou os parâmetros</button></div>
  </section>

  <section id="passo3" hidden>
    <div class="editor">
      <div class="cartao" id="roteiro"></div>
      <div class="cartao chat">
        <h2>Ajuste conversando</h2>
        <div class="sugestoes" id="sugestoes"></div>
        <div class="mensagens" id="mensagens"></div>
        <div class="entrada">
          <input type="text" id="pedido" placeholder="Ex.: deixa o gancho mais provocador">
          <button class="principal" id="enviar">Enviar</button>
        </div>
        <div class="erro" id="erro3" hidden></div>
        <div class="acoes">
          <button class="principal" id="salvar">💾 Salvar na galeria</button>
          <button id="copiar">📋 Copiar</button>
          <button id="voltar2">← Ver as 3 opções</button>
        </div>
        <div class="salvo" id="salvo" hidden></div>
      </div>
    </div>
  </section>
</div>
<script>
const $ = s => document.querySelector(s);
let MENUS = null, opcoes = [], roteiro = null, conversa = [], idSalvo = null, params = {};

function escapar(s) { return String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function etapa(n) {
  [1,2,3].forEach(i => { $('#et'+i).classList.toggle('ativa', i === n); $('#passo'+i).hidden = i !== n; });
  window.scrollTo({top: 0, behavior: 'smooth'});
}
function blocosHtml(r) {
  return (r.blocos || []).map(b => `<div class="bloco"><div class="rotulo">${escapar(b.rotulo)}</div>
    <p class="texto">${escapar(b.texto)}</p>${b.direcao ? `<p class="direcao">🎬 ${escapar(b.direcao)}</p>` : ''}</div>`).join('');
}
function roteiroHtml(r, completo) {
  return `${r.gancho ? `<p class="gancho">🪝 ${escapar(r.gancho)}</p>` : ''}${blocosHtml(r)}` +
    (completo ? `<h2 style="margin-top:16px">Legenda</h2><div class="legenda">${escapar(r.legenda)}</div>
      <div class="tags">${(r.hashtags||[]).map(escapar).join(' ')}</div>` : '');
}
function textoParaCopiar(r) {
  const linhas = [r.titulo, '', r.gancho ? 'GANCHO: ' + r.gancho : ''];
  (r.blocos||[]).forEach(b => { linhas.push('', b.rotulo.toUpperCase(), b.texto); if (b.direcao) linhas.push('  🎬 ' + b.direcao); });
  linhas.push('', 'LEGENDA', r.legenda, '', (r.hashtags||[]).join(' '));
  return linhas.filter(l => l !== undefined).join('\\n');
}

async function carregarMenus() {
  MENUS = await (await fetch('/estudio/menus')).json();
  const opt = (lista, rot) => lista.map(v => `<option value="${escapar(v)}">${escapar(rot ? rot(v) : v)}</option>`).join('');
  $('#formato').innerHTML = opt(Object.keys(MENUS.formatos), k => MENUS.formatos[k]);
  $('#estilo').innerHTML = opt(MENUS.estilos);
  $('#tom').innerHTML = opt(MENUS.tons);
  $('#nicho').innerHTML = opt(MENUS.nichos);
  atualizarTamanhos();
  $('#formato').onchange = atualizarTamanhos;
  const id = new URLSearchParams(location.search).get('id');
  if (id) reabrir(id);
}
function atualizarTamanhos() {
  const f = $('#formato').value;
  $('#tamanho').innerHTML = (MENUS.tamanhos[f] || []).map(v => `<option>${escapar(v)}</option>`).join('');
  if (f === 'video') $('#tamanho').value = '45s';
}
function lerParams() {
  params = { nicho: $('#nicho').value, ideia: $('#ideia').value.trim(), formato: $('#formato').value,
             tamanho: $('#tamanho').value, estilo: $('#estilo').value, tom: $('#tom').value,
             observacoes: $('#obs').value.trim() };
  return params;
}

$('#gerar').onclick = async () => {
  lerParams();
  $('#erro1').hidden = true;
  if (params.ideia.length < 5) { $('#erro1').textContent = 'Escreva a ideia com um pouco mais de detalhe.'; $('#erro1').hidden = false; return; }
  $('#gerar').disabled = true;
  $('#estado1').innerHTML = '<span class="girando"></span>Escrevendo três opções — leva por volta de um minuto…';
  try {
    const r = await (await fetch('/estudio/gerar', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(params)})).json();
    if (!r.ok) throw new Error(r.erro);
    opcoes = r.opcoes; idSalvo = null;
    mostrarOpcoes();
  } catch (e) { $('#erro1').textContent = '⚠️ ' + e.message; $('#erro1').hidden = false; }
  $('#gerar').disabled = false; $('#estado1').textContent = '';
};
function mostrarOpcoes() {
  $('#opcoes').innerHTML = opcoes.map((o, i) => `<div class="cartao opcao">
    <span class="chip">Opção ${i+1}</span><h3>${escapar(o.titulo)}</h3><p class="angulo">${escapar(o.angulo)}</p>
    <div class="previa">${roteiroHtml(o, false)}</div>
    <p class="por-que">📈 ${escapar(o.por_que_funciona)}</p>
    <button class="principal" data-i="${i}">Escolher esta</button></div>`).join('');
  $('#opcoes').querySelectorAll('button[data-i]').forEach(b => b.onclick = () => escolher(+b.dataset.i));
  etapa(2);
}
function escolher(i) {
  roteiro = JSON.parse(JSON.stringify(opcoes[i])); conversa = [];
  $('#mensagens').innerHTML = ''; $('#salvo').hidden = true;
  bolha('ia', `Vamos com "${roteiro.titulo}". Me diga o que ajustar — ou salve como está.`);
  renderRoteiro(); etapa(3);
}
function renderRoteiro() {
  $('#roteiro').innerHTML = `<span class="chip">${escapar(MENUS.formatos[params.formato] || params.formato)}</span>
    <span class="chip">${escapar(params.tom || '')}</span><span class="chip">${escapar(params.tamanho || '')}</span>
    <h3 style="margin:10px 0 4px">${escapar(roteiro.titulo)}</h3><p class="angulo" style="color:var(--suave);font-size:.86rem;margin-bottom:12px">${escapar(roteiro.angulo)}</p>
    ${roteiroHtml(roteiro, true)}`;
  const sug = { video: ['Gancho mais provocador', 'Encurta pra 30s', 'Menos técnico', 'Fecha com pergunta'],
                carrossel: ['Capa mais curta', 'Uma lâmina a menos', 'Menos texto por lâmina', 'CTA pra salvar'],
                stories: ['Põe uma enquete no 2º', 'Primeiro story mais forte', 'Mais bastidor', 'Fecha pedindo DM'] }[params.formato] || [];
  $('#sugestoes').innerHTML = sug.map(s => `<button type="button">${escapar(s)}</button>`).join('');
  $('#sugestoes').querySelectorAll('button').forEach(b => b.onclick = () => { $('#pedido').value = b.textContent; enviar(); });
}
function bolha(quem, texto) {
  const el = document.createElement('div'); el.className = 'msg ' + (quem === 'eu' ? 'eu' : 'ia'); el.textContent = texto;
  $('#mensagens').appendChild(el); $('#mensagens').scrollTop = $('#mensagens').scrollHeight;
}
async function enviar() {
  const msg = $('#pedido').value.trim(); if (!msg) return;
  $('#pedido').value = ''; $('#erro3').hidden = true; bolha('eu', msg);
  $('#enviar').disabled = true;
  const pensando = document.createElement('div'); pensando.className = 'msg ia'; pensando.innerHTML = '<span class="girando"></span>reescrevendo…';
  $('#mensagens').appendChild(pensando);
  try {
    const r = await (await fetch('/estudio/refinar', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({nicho: params.nicho, parametros: params, roteiro, conversa, mensagem: msg})})).json();
    pensando.remove();
    if (!r.ok) throw new Error(r.erro);
    conversa.push({papel:'usuario', texto: msg}, {papel:'ia', texto: r.resposta});
    roteiro = r.roteiro; renderRoteiro(); bolha('ia', r.resposta); $('#salvo').hidden = true;
  } catch (e) { pensando.remove(); $('#erro3').textContent = '⚠️ ' + e.message; $('#erro3').hidden = false; }
  $('#enviar').disabled = false;
}
$('#enviar').onclick = enviar;
$('#pedido').onkeydown = e => { if (e.key === 'Enter') enviar(); };
$('#salvar').onclick = async () => {
  const r = await (await fetch('/galeria/salvar', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({id: idSalvo, nicho: params.nicho, ideia: params.ideia, formato: params.formato,
                          estilo: params.estilo, tom: params.tom, tamanho: params.tamanho, roteiro})})).json();
  if (r.ok) { idSalvo = r.id; $('#salvo').innerHTML = `✅ Salvo na galeria. <a href="/galeria">Ver galeria</a> · <a href="/estudio">Nova ideia</a>`; $('#salvo').hidden = false; }
  else { $('#erro3').textContent = '⚠️ ' + r.erro; $('#erro3').hidden = false; }
};
$('#copiar').onclick = async () => { try { await navigator.clipboard.writeText(textoParaCopiar(roteiro)); bolha('ia', 'Copiado.'); } catch (_) {} };
$('#voltar1').onclick = () => etapa(1);
$('#voltar2').onclick = () => (opcoes.length ? etapa(2) : etapa(1));
async function reabrir(id) {
  const r = await (await fetch('/galeria/itens')).json();
  const item = r.itens.find(i => i.id === id); if (!item) return;
  $('#ideia').value = item.ideia; $('#formato').value = item.formato; atualizarTamanhos();
  $('#tamanho').value = item.tamanho; $('#estilo').value = item.estilo; $('#tom').value = item.tom;
  lerParams(); roteiro = item.roteiro; opcoes = []; conversa = []; idSalvo = id;
  $('#mensagens').innerHTML = ''; bolha('ia', 'Reabri da galeria. O que você quer mudar?'); renderRoteiro(); etapa(3);
}
carregarMenus();
</script></body></html>
""".replace("__ESTILO__", ESTILO_COMUM)
