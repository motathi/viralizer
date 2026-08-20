"""Publica a agenda gerada como página interativa do site (web/index.html).

A página renderiza os roteiros da semana com:
- alternância Reels ⇄ Carrossel por cartão;
- escolha entre as 3 opções de gancho;
- "minha lista" de ideias selecionadas para produzir e marcação de feitas
  (estado salvo no navegador, por semana);
- copiar roteiro/legenda com um clique.
"""

import json
from datetime import date, timedelta
from html import escape
from pathlib import Path

from src.agenda.montador import SLOTS_SEMANA, normalizar_ideia

ESTILO = """
  :root {
    --fundo: #faf7f5; --tinta: #241f28; --suave: #7a7183;
    --acento: #b0578d; --acento-forte: #93446f; --acento-claro: #f6e6f0;
    --card: #ffffff; --borda: #ece4e8; --ok: #2e7d5b; --ok-claro: #e6f2ec;
    --sombra: 0 10px 30px -18px rgba(60, 20, 60, .25);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --fundo: #17131b; --tinta: #f0eaf2; --suave: #a89fb0;
      --acento: #d783b4; --acento-forte: #e79cc6; --acento-claro: #33202c;
      --card: #211b26; --borda: #342b3a; --ok: #6cc39c; --ok-claro: #1d3229;
      --sombra: 0 10px 30px -18px rgba(0, 0, 0, .6);
    }
  }
  * { box-sizing: border-box; margin: 0; }
  html { scroll-behavior: smooth; }
  body { font-family: "Sora", "Segoe UI", system-ui, sans-serif;
         background: var(--fundo); color: var(--tinta); line-height: 1.6; }
  .container { max-width: 880px; margin: 0 auto; padding: 0 18px; }
  header.hero { padding: 44px 0 18px; text-align: center; }
  .selo { display: inline-block; background: var(--acento-claro); color: var(--acento);
          font-size: .78rem; font-weight: 600; padding: 4px 14px; border-radius: 999px;
          letter-spacing: .05em; text-transform: uppercase; margin-bottom: 16px; }
  h1 { font-size: clamp(1.5rem, 5vw, 2.2rem); line-height: 1.25; font-weight: 700; }
  h1 span { color: var(--acento); }
  .sub { color: var(--suave); max-width: 600px; margin: 12px auto 0; font-size: .95rem; }

  .painel { position: sticky; top: 0; z-index: 20; background: var(--fundo);
            padding: 12px 0; border-bottom: 1px solid var(--borda); }
  .painel-linha { display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
                  justify-content: space-between; }
  .abas { display: flex; gap: 6px; background: var(--card); border: 1px solid var(--borda);
          border-radius: 999px; padding: 4px; }
  .aba { border: 0; background: transparent; color: var(--suave); font: inherit;
         font-size: .85rem; font-weight: 600; padding: 6px 14px; border-radius: 999px;
         cursor: pointer; transition: all .18s; }
  .aba.ativa { background: var(--acento); color: #fff; }
  .progresso { font-size: .85rem; color: var(--suave); font-weight: 600; }
  .progresso b { color: var(--ok); }

  section.agenda { padding: 22px 0 70px; }
  .aviso { background: var(--acento-claro); border-radius: 12px; padding: 10px 16px;
           font-size: .84rem; margin-bottom: 24px; }

  .cartao { background: var(--card); border: 1px solid var(--borda); border-radius: 18px;
            padding: 24px 24px 18px; margin-bottom: 22px; box-shadow: var(--sombra);
            transition: opacity .25s, transform .25s; }
  .cartao.feita { opacity: .55; }
  .cartao.oculta { display: none; }
  .topo { display: flex; flex-wrap: wrap; gap: 7px; align-items: center; margin-bottom: 10px; }
  .chip { font-size: .72rem; font-weight: 600; padding: 3px 11px; border-radius: 999px;
          background: var(--acento-claro); color: var(--acento); }
  .chip.dia { background: var(--ok-claro); color: var(--ok); }
  .cartao h3 { font-size: 1.12rem; margin-bottom: 12px; line-height: 1.35; }

  .rotulo { font-size: .74rem; font-weight: 700; text-transform: uppercase;
            letter-spacing: .06em; color: var(--acento); margin: 18px 0 8px; }
  .ganchos { display: flex; flex-direction: column; gap: 8px; }
  .gancho-opcao { display: flex; gap: 10px; align-items: flex-start; background: var(--fundo);
                  border: 1.5px solid var(--borda); border-radius: 12px; padding: 10px 14px;
                  cursor: pointer; font-size: .9rem; transition: border-color .18s; }
  .gancho-opcao:hover { border-color: var(--acento); }
  .gancho-opcao.sel { border-color: var(--acento); background: var(--acento-claro); }
  .gancho-opcao input { accent-color: var(--acento); margin-top: 4px; }

  .segmentos { display: inline-flex; background: var(--fundo); border: 1px solid var(--borda);
               border-radius: 999px; padding: 3px; margin: 4px 0 10px; }
  .seg { border: 0; background: transparent; color: var(--suave); font: inherit;
         font-size: .84rem; font-weight: 600; padding: 6px 16px; border-radius: 999px;
         cursor: pointer; transition: all .18s; }
  .seg.ativa { background: var(--acento); color: #fff; }

  .bloco-tempo { display: grid; grid-template-columns: 64px 1fr; gap: 12px;
                 padding: 10px 0; border-bottom: 1px dashed var(--borda); font-size: .92rem; }
  .bloco-tempo:last-child { border-bottom: 0; }
  .tempo { font-size: .78rem; font-weight: 700; color: var(--acento);
           background: var(--acento-claro); border-radius: 8px; padding: 4px 6px;
           height: fit-content; text-align: center; }
  .direcao { color: var(--suave); font-size: .82rem; margin-top: 4px; }
  .direcao::before { content: "🎥 "; }

  .laminas { counter-reset: lam; display: flex; flex-direction: column; gap: 8px; }
  .lamina { background: var(--fundo); border-radius: 12px; padding: 10px 14px 10px 44px;
            position: relative; font-size: .9rem; }
  .lamina::before { counter-increment: lam; content: counter(lam);
                    position: absolute; left: 12px; top: 10px; width: 22px; height: 22px;
                    border-radius: 50%; background: var(--acento); color: #fff;
                    font-size: .75rem; font-weight: 700; display: flex;
                    align-items: center; justify-content: center; }
  .lamina.capa::before { content: "★"; }
  .lamina.cta::before { content: "➤"; }

  .legenda { background: var(--fundo); border-radius: 12px; padding: 12px 14px;
             font-size: .9rem; white-space: pre-wrap; }
  .hashtags { color: var(--acento); font-size: .85rem; margin-top: 6px; }

  details { margin-top: 14px; border: 1px solid var(--borda); border-radius: 12px;
            padding: 10px 14px; font-size: .9rem; }
  details summary { cursor: pointer; font-weight: 600; font-size: .85rem; color: var(--suave); }
  details[open] summary { margin-bottom: 8px; }
  details ul { padding-left: 18px; }
  details li { margin-bottom: 6px; overflow-wrap: anywhere; }
  .texto { white-space: pre-wrap; }

  .acoes { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px;
           padding-top: 14px; border-top: 1px solid var(--borda); }
  .btn { border: 1.5px solid var(--borda); background: var(--card); color: var(--tinta);
         font: inherit; font-size: .85rem; font-weight: 600; padding: 8px 14px;
         border-radius: 999px; cursor: pointer; transition: all .18s; }
  .btn:hover { border-color: var(--acento); color: var(--acento); }
  .btn.primario { background: var(--acento); border-color: var(--acento); color: #fff; }
  .btn.primario:hover { background: var(--acento-forte); color: #fff; }
  .btn.na-lista { background: var(--acento-claro); border-color: var(--acento); color: var(--acento); }
  .btn.feito-btn.marcado { background: var(--ok-claro); border-color: var(--ok); color: var(--ok); }

  .vazio { text-align: center; color: var(--suave); padding: 40px 0; display: none; }

  #toast { position: fixed; left: 50%; bottom: 26px; transform: translateX(-50%) translateY(80px);
           background: var(--tinta); color: var(--fundo); font-size: .88rem; font-weight: 600;
           padding: 10px 20px; border-radius: 999px; opacity: 0; transition: all .3s;
           z-index: 50; pointer-events: none; }
  #toast.mostrar { transform: translateX(-50%) translateY(0); opacity: 1; }

  footer { border-top: 1px solid var(--borda); padding: 24px 0 40px; text-align: center;
           color: var(--suave); font-size: .84rem; }
"""

SCRIPT = """
const DADOS = JSON.parse(document.getElementById('dados-agenda').textContent);
const CHAVE = 'radar-' + DADOS.semana;
const estado = JSON.parse(localStorage.getItem(CHAVE) || '{}');
let filtro = 'todas';

function salvar() { localStorage.setItem(CHAVE, JSON.stringify(estado)); }
function st(id) { return estado[id] || (estado[id] = {lista: false, feito: false, formato: 'reels', gancho: 0}); }

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('mostrar');
  clearTimeout(t._timer); t._timer = setTimeout(() => t.classList.remove('mostrar'), 2200);
}

function render() {
  let naLista = 0, feitas = 0, visiveis = 0;
  document.querySelectorAll('.cartao').forEach(c => {
    const id = c.dataset.id, s = st(id);
    if (s.lista) naLista++;
    if (s.feito) feitas++;
    c.classList.toggle('feita', s.feito);
    const btnL = c.querySelector('.lista-btn');
    btnL.classList.toggle('na-lista', s.lista);
    btnL.textContent = s.lista ? '✓ Na minha lista' : '+ Adicionar à lista';
    const btnF = c.querySelector('.feito-btn');
    btnF.classList.toggle('marcado', s.feito);
    btnF.textContent = s.feito ? '✓ Feita!' : 'Marcar como feita';
    c.querySelectorAll('.gancho-opcao').forEach((g, i) => {
      g.classList.toggle('sel', i === s.gancho);
      g.querySelector('input').checked = i === s.gancho;
    });
    c.querySelectorAll('.seg').forEach(b => b.classList.toggle('ativa', b.dataset.fmt === s.formato));
    c.querySelector('.painel-reels').style.display = s.formato === 'reels' ? '' : 'none';
    const pc = c.querySelector('.painel-carrossel');
    if (pc) pc.style.display = s.formato === 'carrossel' ? '' : 'none';
    const mostra = filtro === 'todas' || (filtro === 'lista' && s.lista) || (filtro === 'feitas' && s.feito);
    c.classList.toggle('oculta', !mostra);
    if (mostra) visiveis++;
  });
  document.getElementById('contagem').innerHTML =
    `<b>${naLista}</b> na lista · <b>${feitas}</b> feita${feitas === 1 ? '' : 's'}`;
  document.querySelectorAll('.aba').forEach(a => a.classList.toggle('ativa', a.dataset.filtro === filtro));
  document.getElementById('vazio').style.display = visiveis ? 'none' : 'block';
  salvar();
}

function textoRoteiro(id) {
  const d = DADOS.ideias[id], s = st(id);
  let out = d.titulo + '\\n\\n🎣 Gancho: ' + d.ganchos[s.gancho] + '\\n\\n';
  if (s.formato === 'reels') {
    out += '🎬 ROTEIRO (Reels/TikTok)\\n';
    d.reels.forEach(b => {
      out += `\\n[${b.tempo}] ${b.fala}`;
      if (b.direcao) out += `\\n   🎥 ${b.direcao}`;
    });
  } else {
    out += '🖼️ CARROSSEL\\nCapa: ' + d.carrossel.capa;
    d.carrossel.laminas.forEach((l, i) => { out += `\\nLâmina ${i + 1}: ${l}`; });
    out += '\\nCTA final: ' + d.carrossel.cta_final;
  }
  out += '\\n\\n✍️ Legenda:\\n' + d.legenda + '\\n\\n' + d.hashtags.join(' ');
  return out;
}

document.addEventListener('click', e => {
  const c = e.target.closest('.cartao');
  if (e.target.closest('.aba')) { filtro = e.target.closest('.aba').dataset.filtro; render(); return; }
  if (!c) return;
  const id = c.dataset.id, s = st(id);
  if (e.target.closest('.lista-btn')) {
    s.lista = !s.lista;
    if (!s.lista) s.feito = false;
    toast(s.lista ? 'Adicionada à sua lista 📌' : 'Removida da lista');
  } else if (e.target.closest('.feito-btn')) {
    s.feito = !s.feito;
    if (s.feito) s.lista = true;
    toast(s.feito ? 'Boa! Conteúdo feito 🎉' : 'Desmarcada');
  } else if (e.target.closest('.seg')) {
    s.formato = e.target.closest('.seg').dataset.fmt;
  } else if (e.target.closest('.gancho-opcao')) {
    s.gancho = [...c.querySelectorAll('.gancho-opcao')].indexOf(e.target.closest('.gancho-opcao'));
  } else if (e.target.closest('.copiar-btn')) {
    navigator.clipboard.writeText(textoRoteiro(id))
      .then(() => toast('Roteiro copiado 📋'))
      .catch(() => toast('Não foi possível copiar'));
    return;
  } else { return; }
  render();
});

render();
"""


def _cartao(ideia: dict, posicao: int) -> str:
    dia, hora = SLOTS_SEMANA[posicao % len(SLOTS_SEMANA)]
    origem = ideia.get("plataforma_origem_da_tendencia", "")
    carrossel = ideia["roteiro_carrossel"]

    ganchos = "".join(
        f'<label class="gancho-opcao"><input type="radio" name="g{posicao}">'
        f"<span>{escape(g)}</span></label>"
        for g in ideia["ganchos_3s"] if g
    )
    blocos = "".join(
        f'<div class="bloco-tempo"><span class="tempo">{escape(b.get("tempo") or "—")}</span>'
        f'<div><div>{escape(b.get("fala", ""))}</div>'
        + (f'<div class="direcao">{escape(b["direcao"])}</div>' if b.get("direcao") else "")
        + "</div></div>"
        for b in ideia["roteiro_reels"]
    )
    tem_carrossel = bool(carrossel.get("laminas"))
    laminas = ""
    if tem_carrossel:
        laminas = (
            f'<div class="lamina capa"><b>Capa:</b> {escape(carrossel.get("capa", ""))}</div>'
            + "".join(f'<div class="lamina">{escape(l)}</div>' for l in carrossel["laminas"])
            + f'<div class="lamina cta"><b>CTA:</b> {escape(carrossel.get("cta_final", ""))}</div>'
        )
    refs = "".join(f"<li>{escape(r)}</li>" for r in ideia.get("embasamento_cientifico", []))
    hashtags = escape(" ".join(ideia.get("hashtags", [])))

    seletor_formato = (
        f'<div class="segmentos"><button class="seg ativa" data-fmt="reels">🎬 Reels</button>'
        f'<button class="seg" data-fmt="carrossel">🖼️ Carrossel</button></div>'
        if tem_carrossel else ""
    )
    painel_carrossel = (
        f'<div class="painel-carrossel" style="display:none"><div class="laminas">{laminas}</div></div>'
        if tem_carrossel else ""
    )

    return f"""
  <article class="cartao" data-id="{posicao}">
    <div class="topo">
      <span class="chip dia">{escape(dia)} · {escape(hora)}</span>
      <span class="chip">{escape(ideia.get('pilar', ''))}</span>
      <span class="chip">~{ideia.get('duracao_estimada_seg', '?')}s</span>
      {f'<span class="chip">Tendência: {escape(origem)}</span>' if origem else ''}
    </div>
    <h3>{escape(ideia.get('titulo', ''))}</h3>

    <div class="rotulo">Escolha o gancho (3 primeiros segundos)</div>
    <div class="ganchos">{ganchos}</div>

    <div class="rotulo">Roteiro</div>
    {seletor_formato}
    <div class="painel-reels">{blocos}</div>
    {painel_carrossel}

    <div class="rotulo">Legenda pronta</div>
    <div class="legenda">{escape(ideia.get('legenda_post', '')) or escape(ideia.get('cta', ''))}</div>
    <div class="hashtags">{hashtags}</div>

    <details><summary>📈 Por que deve performar</summary>
      <p class="texto">{escape(ideia.get('embasamento_viral', ''))}</p></details>
    <details><summary>🔬 Embasamento científico</summary><ul>{refs}</ul></details>
    <details><summary>⚖️ Conformidade CFM</summary>
      <p class="texto">{escape(ideia.get('conformidade_cfm', ''))}</p></details>

    <div class="acoes">
      <button class="btn primario lista-btn">+ Adicionar à lista</button>
      <button class="btn feito-btn">Marcar como feita</button>
      <button class="btn copiar-btn">📋 Copiar roteiro</button>
    </div>
  </article>"""


def publicar_site(config: dict, roteiros: dict, sinais: dict, destino: Path) -> None:
    """Escreve a agenda da semana como web/index.html."""
    ideias = [normalizar_ideia(i) for i in roteiros["ideias"]]
    total_sinais = sum(len(v) for v in sinais.values())
    inicio = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 or 7)
    cartoes = "".join(_cartao(ideia, i) for i, ideia in enumerate(ideias))

    dados = {
        "semana": inicio.isoformat(),
        "ideias": [
            {
                "titulo": i["titulo"],
                "ganchos": i["ganchos_3s"],
                "reels": i["roteiro_reels"],
                "carrossel": i["roteiro_carrossel"],
                "legenda": i.get("legenda_post") or i.get("cta", ""),
                "hashtags": i.get("hashtags", []),
            }
            for i in ideias
        ],
    }

    dados_json = json.dumps(dados, ensure_ascii=False).replace("</", "<\\/")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Radar de Conteúdo Viral — {escape(config['nome'])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&display=swap" rel="stylesheet">
<style>{ESTILO}</style>
</head>
<body>
<header class="hero container">
  <div class="selo">Radar de Conteúdo Viral</div>
  <h1>Agenda da semana — <span>{escape(config['nome'])}</span></h1>
  <p class="sub">Semana de {inicio.strftime('%d/%m/%Y')} · {len(ideias)} conteúdos ·
  {total_sinais} sinais de tendência analisados · atualizada em {date.today().strftime('%d/%m/%Y')}</p>
</header>

<div class="painel">
  <div class="container painel-linha">
    <div class="abas">
      <button class="aba ativa" data-filtro="todas">Todas</button>
      <button class="aba" data-filtro="lista">📌 Minha lista</button>
      <button class="aba" data-filtro="feitas">✓ Feitas</button>
    </div>
    <div class="progresso" id="contagem"></div>
  </div>
</div>

<section class="agenda container">
  <div class="aviso">⚕️ Todo conteúdo é um rascunho embasado: a palavra final sobre
  qualquer afirmação médica é sempre da profissional.</div>
  {cartoes}
  <p class="vazio" id="vazio">Nada por aqui ainda — adicione ideias à sua lista. 📌</p>
</section>

<footer>
  <div class="container">
    <p><strong>Radar de Conteúdo Viral</strong> — pesquisa de tendências, roteiros embasados e agenda semanal.</p>
  </div>
</footer>

<div id="toast"></div>
<script id="dados-agenda" type="application/json">{dados_json}</script>
<script>{SCRIPT}</script>
</body>
</html>
"""
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
