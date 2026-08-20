"""Publica a agenda gerada como página interativa do site (web/index.html).

A página renderiza os roteiros da semana com:
- cards compactos em grade que expandem ao clicar;
- alternância Reels ⇄ Carrossel e escolha entre as 3 opções de gancho
  (o gancho escolhido substitui o bloco de abertura do roteiro);
- "minha lista" de ideias selecionadas e marcação de feitas (estado salvo
  no navegador, por semana), com filtros e contador;
- copiar roteiro e link compartilhável de um roteiro só (#r<n>).
"""

import json
from datetime import date, timedelta
from html import escape
from pathlib import Path

from src.agenda.montador import normalizar_ideia, slot_para

ESTILO = """
  :root {
    --fundo: #ffffff; --tinta: #1d1a20; --suave: #6f6a76;
    --acento: #b0578d; --acento-forte: #93446f; --acento-claro: #faeef5;
    --card: #ffffff; --borda: #e8e5ea; --ok: #2e7d5b; --ok-claro: #e9f4ee;
    --sombra: 0 1px 3px rgba(35, 20, 35, .06);
    --sombra-alta: 0 12px 34px -14px rgba(35, 20, 35, .22);
  }
  * { box-sizing: border-box; margin: 0; }
  html { scroll-behavior: smooth; }
  body { font-family: "Sora", "Segoe UI", system-ui, sans-serif;
         background: var(--fundo); color: var(--tinta); line-height: 1.6; }
  .container { max-width: 1020px; margin: 0 auto; padding: 0 18px; }
  header.hero { padding: 40px 0 16px; text-align: center; }
  .selo { display: inline-block; background: var(--acento-claro); color: var(--acento);
          font-size: .76rem; font-weight: 600; padding: 4px 14px; border-radius: 999px;
          letter-spacing: .05em; text-transform: uppercase; margin-bottom: 14px; }
  h1 { font-size: clamp(1.4rem, 4.5vw, 2rem); line-height: 1.25; font-weight: 700; }
  h1 span { color: var(--acento); }
  .sub { color: var(--suave); max-width: 620px; margin: 10px auto 0; font-size: .92rem; }

  .painel { position: sticky; top: 0; z-index: 20; background: rgba(255,255,255,.92);
            backdrop-filter: blur(8px); padding: 10px 0; border-bottom: 1px solid var(--borda); }
  .painel-linha { display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
                  justify-content: space-between; }
  .abas { display: flex; gap: 4px; background: #f4f2f5; border-radius: 999px; padding: 4px; }
  .aba { border: 0; background: transparent; color: var(--suave); font: inherit;
         font-size: .84rem; font-weight: 600; padding: 6px 14px; border-radius: 999px;
         cursor: pointer; transition: all .18s; }
  .aba.ativa { background: var(--acento); color: #fff; }
  .progresso { font-size: .84rem; color: var(--suave); font-weight: 600; }
  .progresso b { color: var(--ok); }

  #banner-foco { display: none; background: var(--acento-claro); border-radius: 12px;
                 padding: 12px 16px; margin: 18px 0 0; font-size: .9rem;
                 align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
  body.em-foco #banner-foco { display: flex; }
  body.em-foco .painel, body.em-foco .aviso { display: none; }

  section.agenda { padding: 20px 0 70px; }
  .aviso { background: var(--acento-claro); border-radius: 12px; padding: 10px 16px;
           font-size: .83rem; margin-bottom: 20px; }

  .lista-cartoes { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
                   gap: 14px; align-items: start; }

  .cartao { background: var(--card); border: 1px solid var(--borda); border-radius: 16px;
            box-shadow: var(--sombra); transition: box-shadow .2s, border-color .2s; }
  .cartao.oculta { display: none; }
  .cartao.aberta { grid-column: 1 / -1; box-shadow: var(--sombra-alta); }
  .cartao.feita .cab { opacity: .55; }
  .cartao.feita .cab h3 { text-decoration: line-through; }

  .cab { padding: 16px 18px 14px; cursor: pointer; position: relative; }
  .cab:hover { background: #fdfbfc; border-radius: 16px; }
  .topo { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 8px;
          padding-right: 26px; }
  .chip { font-size: .7rem; font-weight: 600; padding: 2px 10px; border-radius: 999px;
          background: var(--acento-claro); color: var(--acento); }
  .chip.dia { background: var(--ok-claro); color: var(--ok); }
  .chip-status { display: none; }
  .cartao.na-lista .chip-status.lista { display: inline-block; background: var(--acento); color: #fff; }
  .cartao.feita .chip-status.feito { display: inline-block; background: var(--ok); color: #fff; }
  .cab h3 { font-size: 1.02rem; line-height: 1.4; font-weight: 600; }
  .previa { color: var(--suave); font-size: .84rem; margin-top: 6px; font-style: italic;
            display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
            overflow: hidden; }
  .seta { position: absolute; right: 16px; top: 16px; color: var(--suave);
          transition: transform .25s; font-size: .8rem; }
  .cartao.aberta .seta { transform: rotate(180deg); }
  .cartao.aberta .previa { display: none; }

  .detalhe { display: none; padding: 0 20px 18px; border-top: 1px solid var(--borda); }
  .cartao.aberta .detalhe { display: block; }

  .rotulo { font-size: .72rem; font-weight: 700; text-transform: uppercase;
            letter-spacing: .06em; color: var(--acento); margin: 16px 0 8px; }
  .ganchos { display: flex; flex-direction: column; gap: 8px; }
  .gancho-opcao { display: flex; gap: 10px; align-items: flex-start; background: #faf9fb;
                  border: 1.5px solid var(--borda); border-radius: 12px; padding: 10px 14px;
                  cursor: pointer; font-size: .88rem; transition: border-color .18s; }
  .gancho-opcao:hover { border-color: var(--acento); }
  .gancho-opcao.sel { border-color: var(--acento); background: var(--acento-claro); }
  .gancho-opcao input { accent-color: var(--acento); margin-top: 4px; }

  .segmentos { display: inline-flex; background: #f4f2f5; border-radius: 999px;
               padding: 3px; margin: 2px 0 10px; }
  .seg { border: 0; background: transparent; color: var(--suave); font: inherit;
         font-size: .82rem; font-weight: 600; padding: 6px 16px; border-radius: 999px;
         cursor: pointer; transition: all .18s; }
  .seg.ativa { background: var(--acento); color: #fff; }

  .bloco-tempo { display: grid; grid-template-columns: 62px 1fr; gap: 12px;
                 padding: 9px 0; border-bottom: 1px dashed var(--borda); font-size: .9rem; }
  .bloco-tempo:last-child { border-bottom: 0; }
  .tempo { font-size: .74rem; font-weight: 700; color: var(--acento);
           background: var(--acento-claro); border-radius: 8px; padding: 4px 6px;
           height: fit-content; text-align: center; }
  .direcao { color: var(--suave); font-size: .8rem; margin-top: 3px; }
  .direcao::before { content: "🎥 "; }

  .laminas { counter-reset: lam; display: flex; flex-direction: column; gap: 8px; }
  .lamina { background: #faf9fb; border-radius: 12px; padding: 10px 14px 10px 44px;
            position: relative; font-size: .88rem; }
  .lamina::before { counter-increment: lam; content: counter(lam);
                    position: absolute; left: 12px; top: 10px; width: 22px; height: 22px;
                    border-radius: 50%; background: var(--acento); color: #fff;
                    font-size: .73rem; font-weight: 700; display: flex;
                    align-items: center; justify-content: center; }
  .lamina.capa::before { content: "★"; }
  .lamina.cta::before { content: "➤"; }

  .legenda { background: #faf9fb; border-radius: 12px; padding: 12px 14px;
             font-size: .88rem; white-space: pre-wrap; }
  .hashtags { color: var(--acento); font-size: .84rem; margin-top: 6px; }

  .virais-origem { display: flex; flex-direction: column; gap: 8px; }
  .viral-item { background: #faf9fb; border-radius: 12px; padding: 10px 14px;
                font-size: .86rem; }
  .viral-item a { color: var(--acento); font-weight: 600; text-decoration: none; }
  .viral-item a:hover { text-decoration: underline; }
  .viral-item .metrica { color: var(--ok); font-weight: 600; }
  .viral-item .motivo { color: var(--suave); display: block; margin-top: 2px; }
  .padrao { background: var(--acento-claro); border-radius: 12px; padding: 10px 14px;
            font-size: .86rem; margin-top: 8px; }

  details { margin-top: 12px; border: 1px solid var(--borda); border-radius: 12px;
            padding: 10px 14px; font-size: .88rem; }
  details summary { cursor: pointer; font-weight: 600; font-size: .83rem; color: var(--suave); }
  details[open] summary { margin-bottom: 8px; }
  details ul { padding-left: 18px; }
  details li { margin-bottom: 6px; overflow-wrap: anywhere; }
  .texto { white-space: pre-wrap; }

  .acoes { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px;
           padding-top: 14px; border-top: 1px solid var(--borda); }
  .btn { border: 1.5px solid var(--borda); background: #fff; color: var(--tinta);
         font: inherit; font-size: .83rem; font-weight: 600; padding: 8px 14px;
         border-radius: 999px; cursor: pointer; transition: all .18s; }
  .btn:hover { border-color: var(--acento); color: var(--acento); }
  .btn.primario { background: var(--acento); border-color: var(--acento); color: #fff; }
  .btn.primario:hover { background: var(--acento-forte); color: #fff; }
  .btn.na-lista-btn { background: var(--acento-claro); border-color: var(--acento); color: var(--acento); }
  .btn.feito-btn.marcado { background: var(--ok-claro); border-color: var(--ok); color: var(--ok); }

  .vazio { text-align: center; color: var(--suave); padding: 40px 0; display: none; }

  #toast { position: fixed; left: 50%; bottom: 26px; transform: translateX(-50%) translateY(80px);
           background: var(--tinta); color: #fff; font-size: .87rem; font-weight: 600;
           padding: 10px 20px; border-radius: 999px; opacity: 0; transition: all .3s;
           z-index: 50; pointer-events: none; max-width: 90vw; }
  #toast.mostrar { transform: translateX(-50%) translateY(0); opacity: 1; }

  footer { border-top: 1px solid var(--borda); padding: 24px 0 40px; text-align: center;
           color: var(--suave); font-size: .83rem; }
"""

SCRIPT = """
const DADOS = JSON.parse(document.getElementById('dados-agenda').textContent);
const CHAVE = 'radar-' + DADOS.semana;
const estado = JSON.parse(localStorage.getItem(CHAVE) || '{}');
const abertas = new Set();
let filtro = 'todas';
let foco = null;

function salvar() { localStorage.setItem(CHAVE, JSON.stringify(estado)); }
function st(id) { return estado[id] || (estado[id] = {lista: false, feito: false, formato: 'reels', gancho: 0}); }

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('mostrar');
  clearTimeout(t._timer); t._timer = setTimeout(() => t.classList.remove('mostrar'), 2400);
}

function lerHash() {
  const m = location.hash.match(/^#r(\\d+)$/);
  foco = m && DADOS.ideias[m[1]] ? m[1] : null;
  if (foco !== null) abertas.add(foco);
  document.body.classList.toggle('em-foco', foco !== null);
}

function render() {
  let naLista = 0, feitas = 0, visiveis = 0;
  document.querySelectorAll('.cartao').forEach(c => {
    const id = c.dataset.id, s = st(id), d = DADOS.ideias[id];
    if (s.lista) naLista++;
    if (s.feito) feitas++;
    c.classList.toggle('feita', s.feito);
    c.classList.toggle('na-lista', s.lista);
    c.classList.toggle('aberta', abertas.has(id));
    const btnL = c.querySelector('.na-lista-btn2');
    btnL.classList.toggle('na-lista-btn', s.lista);
    btnL.textContent = s.lista ? '✓ Na minha lista' : '+ Adicionar à lista';
    const btnF = c.querySelector('.feito-btn');
    btnF.classList.toggle('marcado', s.feito);
    btnF.textContent = s.feito ? '✓ Feita!' : 'Marcar como feita';
    c.querySelectorAll('.gancho-opcao').forEach((g, i) => {
      g.classList.toggle('sel', i === s.gancho);
      g.querySelector('input').checked = i === s.gancho;
    });
    // o gancho escolhido substitui a fala do bloco de abertura do roteiro
    const abertura = c.querySelector('.fala-gancho');
    if (abertura) abertura.textContent = d.ganchos[s.gancho] || d.ganchos[0];
    const previa = c.querySelector('.previa');
    if (previa) previa.textContent = '🎣 ' + (d.ganchos[s.gancho] || '');
    c.querySelectorAll('.seg').forEach(b => b.classList.toggle('ativa', b.dataset.fmt === s.formato));
    const pr = c.querySelector('.painel-reels'), pc = c.querySelector('.painel-carrossel');
    if (pr) pr.style.display = s.formato === 'reels' ? '' : 'none';
    if (pc) pc.style.display = s.formato === 'carrossel' ? '' : 'none';
    const passaFiltro = filtro === 'todas' || (filtro === 'lista' && s.lista) || (filtro === 'feitas' && s.feito);
    const mostra = foco !== null ? id === foco : passaFiltro;
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
  const gancho = d.ganchos[s.gancho] || d.ganchos[0];
  let out = d.titulo + '\\n\\n🎣 Gancho: ' + gancho + '\\n\\n';
  if (s.formato === 'reels' || !d.carrossel.laminas.length) {
    out += '🎬 ROTEIRO (Reels/TikTok)\\n';
    d.reels.forEach((b, i) => {
      out += `\\n[${b.tempo}] ${i === 0 ? gancho : b.fala}`;
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

function copiar(texto, msgOk) {
  navigator.clipboard.writeText(texto)
    .then(() => toast(msgOk))
    .catch(() => window.prompt('Copie manualmente:', texto));
}

document.getElementById('sair-foco').addEventListener('click', () => {
  history.replaceState(null, '', location.pathname);
  lerHash(); render();
});
window.addEventListener('hashchange', () => { lerHash(); render(); });

document.addEventListener('click', e => {
  const aba = e.target.closest('.aba');
  if (aba) { filtro = aba.dataset.filtro; render(); return; }
  const c = e.target.closest('.cartao');
  if (!c) return;
  const id = c.dataset.id, s = st(id);
  if (e.target.closest('.cab')) {
    abertas.has(id) ? abertas.delete(id) : abertas.add(id);
  } else if (e.target.closest('.na-lista-btn2')) {
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
    copiar(textoRoteiro(id), 'Roteiro copiado 📋'); return;
  } else if (e.target.closest('.compartilhar-btn')) {
    const link = location.origin + location.pathname + '#r' + id;
    copiar(link, 'Link do roteiro copiado 🔗'); return;
  } else { return; }
  render();
});

lerHash();
render();
"""


def _cartao(ideia: dict, posicao: int) -> str:
    dia, hora = slot_para(posicao)
    chip_dia = f"{escape(dia)} · {escape(hora)}" if hora else escape(dia)
    origem = ideia.get("plataforma_origem_da_tendencia", "")
    carrossel = ideia["roteiro_carrossel"]

    ganchos = "".join(
        f'<label class="gancho-opcao"><input type="radio" name="g{posicao}">'
        f"<span>{escape(g)}</span></label>"
        for g in ideia["ganchos_3s"] if g
    )
    blocos = "".join(
        f'<div class="bloco-tempo"><span class="tempo">{escape(b.get("tempo") or "—")}</span>'
        f'<div><div{" class=" + chr(34) + "fala-gancho" + chr(34) if i == 0 else ""}>{escape(b.get("fala", ""))}</div>'
        + (f'<div class="direcao">{escape(b["direcao"])}</div>' if b.get("direcao") else "")
        + "</div></div>"
        for i, b in enumerate(ideia["roteiro_reels"])
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

    virais_html = ""
    if ideia["virais_origem"]:
        itens = "".join(
            '<div class="viral-item">'
            + (f'<a href="{escape(v["url"], quote=True)}" target="_blank" rel="noopener">'
               f'{escape(v.get("autor") or "ver vídeo")} ↗</a>' if v.get("url")
               else f'<b>{escape(v.get("autor", ""))}</b>')
            + (f' · <span class="metrica">{escape(v["metrica"])}</span>' if v.get("metrica") else "")
            + (f'<span class="motivo">{escape(v["por_que_viralizou"])}</span>'
               if v.get("por_que_viralizou") else "")
            + "</div>"
            for v in ideia["virais_origem"]
        )
        padrao = (f'<div class="padrao">🧩 <b>Padrão aplicado:</b> '
                  f'{escape(ideia["padrao_aplicado"])}</div>'
                  if ideia.get("padrao_aplicado") else "")
        virais_html = (
            '<div class="rotulo">🎯 Virais que inspiraram esta ideia</div>'
            f'<div class="virais-origem">{itens}</div>{padrao}'
        )

    seletor_formato = (
        '<div class="segmentos"><button class="seg ativa" data-fmt="reels">🎬 Reels</button>'
        '<button class="seg" data-fmt="carrossel">🖼️ Carrossel</button></div>'
        if tem_carrossel else ""
    )
    painel_carrossel = (
        f'<div class="painel-carrossel" style="display:none"><div class="laminas">{laminas}</div></div>'
        if tem_carrossel else ""
    )

    return f"""
  <article class="cartao" data-id="{posicao}" id="r{posicao}">
    <div class="cab">
      <span class="seta">▼</span>
      <div class="topo">
        <span class="chip dia">{chip_dia}</span>
        <span class="chip">{escape(ideia.get('pilar', '').split('(')[0].strip())}</span>
        <span class="chip">~{ideia.get('duracao_estimada_seg', '?')}s</span>
        {f'<span class="chip">Tendência: {escape(origem)}</span>' if origem else ''}
        <span class="chip chip-status lista">📌 na lista</span>
        <span class="chip chip-status feito">✓ feita</span>
      </div>
      <h3>{escape(ideia.get('titulo', ''))}</h3>
      <p class="previa"></p>
    </div>
    <div class="detalhe">
      <div class="rotulo">Escolha o gancho (3 primeiros segundos)</div>
      <div class="ganchos">{ganchos}</div>

      <div class="rotulo">Roteiro</div>
      {seletor_formato}
      <div class="painel-reels">{blocos}</div>
      {painel_carrossel}

      {virais_html}

      <div class="rotulo">Legenda pronta</div>
      <div class="legenda">{escape(ideia.get('legenda_post', '')) or escape(ideia.get('cta', ''))}</div>
      <div class="hashtags">{hashtags}</div>

      <details><summary>📈 Por que deve performar</summary>
        <p class="texto">{escape(ideia.get('embasamento_viral', ''))}</p></details>
      <details><summary>🔬 Embasamento científico</summary><ul>{refs}</ul></details>
      <details><summary>⚖️ Conformidade CFM</summary>
        <p class="texto">{escape(ideia.get('conformidade_cfm', ''))}</p></details>

      <div class="acoes">
        <button class="btn primario na-lista-btn2">+ Adicionar à lista</button>
        <button class="btn feito-btn">Marcar como feita</button>
        <button class="btn copiar-btn">📋 Copiar roteiro</button>
        <button class="btn compartilhar-btn">🔗 Compartilhar</button>
      </div>
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
                "ganchos": [g for g in i["ganchos_3s"] if g],
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
  <p class="sub">Semana de {inicio.strftime('%d/%m/%Y')} · {len(ideias)} ideias ·
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
  <div id="banner-foco">
    <span>🔗 Você está vendo um roteiro compartilhado.</span>
    <button class="btn" id="sair-foco">Ver a agenda completa</button>
  </div>
  <div class="aviso">⚕️ Todo conteúdo é um rascunho embasado: a palavra final sobre
  qualquer afirmação médica é sempre da profissional. Toque em um card para abrir o roteiro.</div>
  <div class="lista-cartoes">{cartoes}</div>
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
