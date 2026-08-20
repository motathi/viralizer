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
import re
from datetime import date, timedelta
from html import escape
from pathlib import Path

from src.agenda.montador import normalizar_ideia, slot_para

ESTILO = """  :root {
    /* Design tokens — paleta oficial do Instagram */
    --ig-blue: #405DE6; --ig-purple: #833AB4; --ig-magenta: #C13584;
    --ig-pink: #E1306C; --ig-orange: #F77737; --ig-yellow: #FCAF45;
    --grad: linear-gradient(45deg, #405DE6 0%, #833AB4 30%, #C13584 50%, #E1306C 70%, #F77737 100%);
    --grad-suave: linear-gradient(45deg, #f5f1fe, #fdeef5, #fff4ec);

    /* Neutros (escala do Instagram) */
    --fundo: #ffffff; --superficie: #fafafa; --tinta: #262626;
    --suave: #737373; --borda: #dbdbdb; --borda-leve: #efefef;
    --acento: #C13584; --ok: #1f9d63; --ok-claro: #e8f6ef;

    /* Elevação e forma */
    --r-lg: 20px; --r-md: 14px; --r-full: 999px;
    --sombra-1: 0 1px 2px rgba(0,0,0,.05);
    --sombra-2: 0 8px 24px -8px rgba(131, 58, 180, .16);
    --sombra-3: 0 18px 44px -16px rgba(131, 58, 180, .28);
  }
  * { box-sizing: border-box; margin: 0; }
  html { scroll-behavior: smooth; }
  body { font-family: "Inter", "Segoe UI", system-ui, sans-serif;
         background: var(--fundo); color: var(--tinta); line-height: 1.6;
         -webkit-font-smoothing: antialiased; }
  .container { max-width: 1020px; margin: 0 auto; padding: 0 18px; }
  button { font-family: inherit; }
  :focus-visible { outline: 2px solid var(--ig-purple); outline-offset: 2px; border-radius: 4px; }

  header.hero { padding: 44px 0 18px; text-align: center; }
  .selo { display: inline-flex; align-items: center; gap: 8px; font-size: .78rem;
          font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
          padding: 6px 16px; border-radius: var(--r-full); margin-bottom: 16px;
          color: var(--tinta); position: relative; background:
            linear-gradient(var(--fundo), var(--fundo)) padding-box,
            var(--grad) border-box; border: 2px solid transparent; }
  .selo::before { content: ""; width: 10px; height: 10px; border-radius: 50%;
                  background: var(--grad); }
  h1 { font-size: clamp(1.5rem, 4.5vw, 2.2rem); line-height: 1.22;
       font-weight: 800; letter-spacing: -.02em; }
  h1 span { background: var(--grad); -webkit-background-clip: text;
            background-clip: text; -webkit-text-fill-color: transparent; }
  .sub { color: var(--suave); max-width: 640px; margin: 12px auto 0; font-size: .93rem; }

  .painel { position: sticky; top: 0; z-index: 20; background: rgba(255,255,255,.86);
            backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
            padding: 10px 0; border-bottom: 1px solid var(--borda-leve); }
  .painel-linha { display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
                  justify-content: space-between; }
  .abas { display: flex; gap: 4px; background: var(--superficie);
          border: 1px solid var(--borda-leve); border-radius: var(--r-full); padding: 4px; }
  .aba { border: 0; background: transparent; color: var(--suave); font-size: .84rem;
         font-weight: 600; padding: 7px 15px; border-radius: var(--r-full);
         cursor: pointer; transition: all .2s; }
  .aba:hover { color: var(--tinta); }
  .aba.ativa { background: var(--grad); color: #fff; box-shadow: var(--sombra-2); }
  .progresso { font-size: .84rem; color: var(--suave); font-weight: 600; }
  .progresso b { background: var(--grad); -webkit-background-clip: text;
                 background-clip: text; -webkit-text-fill-color: transparent;
                 font-weight: 800; }

  #banner-foco { display: none; border-radius: var(--r-md); padding: 14px 18px;
                 margin: 18px 0 0; font-size: .9rem; align-items: center;
                 justify-content: space-between; gap: 10px; flex-wrap: wrap;
                 background: var(--grad-suave); border: 1px solid var(--borda-leve); }
  body.em-foco #banner-foco { display: flex; }
  body.em-foco .painel, body.em-foco .aviso { display: none; }

  section.agenda { padding: 22px 0 70px; }
  .aviso { background: var(--grad-suave); border-radius: var(--r-md);
           padding: 11px 16px; font-size: .83rem; margin-bottom: 22px; }

  .lista-cartoes { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
                   gap: 16px; align-items: start; }

  .cartao { background: var(--fundo); border: 1px solid var(--borda);
            border-radius: var(--r-lg); box-shadow: var(--sombra-1);
            transition: box-shadow .25s, transform .25s, border-color .25s;
            position: relative; overflow: hidden; }
  .cartao::before { content: ""; position: absolute; inset: 0 0 auto 0; height: 3px;
                    background: var(--grad); opacity: 0; transition: opacity .25s; }
  .cartao:hover { transform: translateY(-2px); box-shadow: var(--sombra-2); }
  .cartao:hover::before, .cartao.aberta::before { opacity: 1; }
  .cartao.oculta { display: none; }
  .cartao.aberta { grid-column: 1 / -1; box-shadow: var(--sombra-3);
                   border-color: transparent; transform: none; }
  .cartao.feita .cab { opacity: .5; }
  .cartao.feita .cab h3 { text-decoration: line-through; }

  .cab { padding: 18px 18px 15px; cursor: pointer; position: relative; }
  .topo { display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
          margin-bottom: 9px; padding-right: 28px; }
  .chip { font-size: .7rem; font-weight: 600; padding: 3px 11px;
          border-radius: var(--r-full); background: var(--superficie);
          border: 1px solid var(--borda-leve); color: var(--suave); }
  .chip.dia { background: var(--ok-claro); border-color: transparent; color: var(--ok); }
  .chip.views { background: var(--grad); border: 0; color: #fff; font-weight: 800;
                letter-spacing: .01em; }
  .chip.plataforma { display: inline-flex; align-items: center; gap: 5px;
                     padding: 4px 10px; background: var(--fundo);
                     border: 1px solid var(--borda-leve); }
  .chip.plataforma svg { width: 15px; height: 15px; display: block; }
  .viral-item .logo { width: 14px; height: 14px; vertical-align: -2px;
                      margin-right: 5px; display: inline-block; }
  .chip.trend { color: var(--acento); background:
                  linear-gradient(var(--fundo), var(--fundo)) padding-box,
                  var(--grad) border-box; border: 1.5px solid transparent; }
  .chip-status { display: none; }
  .cartao.na-lista .chip-status.lista { display: inline-block; background: var(--grad);
                                        border: 0; color: #fff; }
  .cartao.feita .chip-status.feito { display: inline-block; background: var(--ok);
                                     border: 0; color: #fff; }
  .cab h3 { font-size: 1.03rem; line-height: 1.4; font-weight: 700; letter-spacing: -.01em; }
  .previa { color: var(--suave); font-size: .84rem; margin-top: 7px; font-style: italic;
            display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
            overflow: hidden; }
  .seta { position: absolute; right: 18px; top: 18px; color: var(--suave);
          transition: transform .3s cubic-bezier(.34,1.56,.64,1); font-size: .8rem; }
  .cartao.aberta .seta { transform: rotate(180deg); }
  .cartao.aberta .previa { display: none; }

  .detalhe { display: none; padding: 0 22px 20px; border-top: 1px solid var(--borda-leve); }
  .cartao.aberta .detalhe { display: block; animation: abrir .3s ease; }
  @keyframes abrir { from { opacity: 0; transform: translateY(-6px); }
                     to { opacity: 1; transform: none; } }

  .rotulo { font-size: .72rem; font-weight: 800; text-transform: uppercase;
            letter-spacing: .08em; margin: 20px 0 9px;
            background: var(--grad); -webkit-background-clip: text;
            background-clip: text; -webkit-text-fill-color: transparent; }
  .ganchos { display: flex; flex-direction: column; gap: 8px; }
  .gancho-opcao { display: flex; gap: 10px; align-items: flex-start;
                  background: var(--superficie); border: 1.5px solid var(--borda-leve);
                  border-radius: var(--r-md); padding: 11px 14px; cursor: pointer;
                  font-size: .89rem; transition: all .2s; }
  .gancho-opcao:hover { border-color: var(--borda); transform: translateX(2px); }
  .gancho-opcao.sel { background:
                        linear-gradient(var(--fundo), var(--fundo)) padding-box,
                        var(--grad) border-box; border: 1.5px solid transparent;
                      box-shadow: var(--sombra-1); }
  .gancho-opcao input { accent-color: var(--ig-magenta); margin-top: 4px; }

  .segmentos { display: inline-flex; background: var(--superficie);
               border: 1px solid var(--borda-leve); border-radius: var(--r-full);
               padding: 3px; margin: 2px 0 12px; }
  .seg { border: 0; background: transparent; color: var(--suave); font-size: .83rem;
         font-weight: 600; padding: 7px 17px; border-radius: var(--r-full);
         cursor: pointer; transition: all .2s; }
  .seg.ativa { background: var(--grad); color: #fff; box-shadow: var(--sombra-2); }

  .bloco-tempo { display: grid; grid-template-columns: 64px 1fr; gap: 13px;
                 padding: 10px 0; border-bottom: 1px dashed var(--borda-leve);
                 font-size: .9rem; }
  .bloco-tempo:last-child { border-bottom: 0; }
  .tempo { font-size: .73rem; font-weight: 800; color: #fff; background: var(--grad);
           border-radius: 9px; padding: 4px 6px; height: fit-content; text-align: center;
           letter-spacing: .02em; }
  .direcao { color: var(--suave); font-size: .8rem; margin-top: 3px; }
  .direcao::before { content: "🎥 "; }

  .laminas { counter-reset: lam; display: flex; flex-direction: column; gap: 8px; }
  .lamina { background: var(--superficie); border-radius: var(--r-md);
            padding: 11px 14px 11px 46px; position: relative; font-size: .89rem; }
  .lamina::before { counter-increment: lam; content: counter(lam);
                    position: absolute; left: 12px; top: 10px; width: 24px; height: 24px;
                    border-radius: 50%; background: var(--grad); color: #fff;
                    font-size: .73rem; font-weight: 800; display: flex;
                    align-items: center; justify-content: center; }
  .lamina.capa::before { content: "★"; }
  .lamina.cta::before { content: "➤"; }

  .legenda { background: var(--superficie); border-radius: var(--r-md);
             padding: 13px 15px; font-size: .89rem; white-space: pre-wrap; }
  .hashtags { font-size: .85rem; margin-top: 7px; font-weight: 600;
              background: var(--grad); -webkit-background-clip: text;
              background-clip: text; -webkit-text-fill-color: transparent; }

  .virais-origem { display: flex; flex-direction: column; gap: 8px; }
  .viral-item { background: var(--superficie); border-radius: var(--r-md);
                padding: 11px 15px; font-size: .86rem;
                border: 1px solid var(--borda-leve);
                border-left: 3px solid var(--ig-magenta); }
  .viral-item a { color: var(--ig-magenta); font-weight: 700; text-decoration: none; }
  .viral-item a:hover { text-decoration: underline; }
  .viral-item .metrica { color: var(--ok); font-weight: 700; }
  .viral-item .motivo { color: var(--suave); display: block; margin-top: 2px; }
  .padrao { background: var(--grad-suave); border-radius: var(--r-md);
            padding: 11px 15px; font-size: .86rem; margin-top: 8px; }

  details { margin-top: 12px; border: 1px solid var(--borda-leve);
            border-radius: var(--r-md); padding: 11px 15px; font-size: .88rem;
            background: var(--fundo); transition: background .2s; }
  details:hover { background: var(--superficie); }
  details summary { cursor: pointer; font-weight: 700; font-size: .83rem; color: var(--suave); }
  details[open] summary { margin-bottom: 8px; }
  details ul { padding-left: 18px; }
  details li { margin-bottom: 6px; overflow-wrap: anywhere; }
  .texto { white-space: pre-wrap; }

  .acoes { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px;
           padding-top: 16px; border-top: 1px solid var(--borda-leve); }
  .btn { border: 1.5px solid var(--borda); background: var(--fundo); color: var(--tinta);
         font-size: .84rem; font-weight: 700; padding: 9px 16px;
         border-radius: var(--r-full); cursor: pointer; transition: all .2s; }
  .btn:hover { border-color: var(--ig-magenta); color: var(--ig-magenta);
               transform: translateY(-1px); }
  .btn.primario { background: var(--grad); border-color: transparent; color: #fff;
                  box-shadow: var(--sombra-2); }
  .btn.primario:hover { color: #fff; filter: brightness(1.06); box-shadow: var(--sombra-3); }
  .btn.na-lista-btn { background: var(--grad-suave); border: 1.5px solid transparent;
                      background-origin: border-box; color: var(--ig-magenta); }
  .btn.feito-btn.marcado { background: var(--ok-claro); border-color: var(--ok); color: var(--ok); }

  .vazio { text-align: center; color: var(--suave); padding: 44px 0; display: none; }

  #toast { position: fixed; left: 50%; bottom: 28px;
           transform: translateX(-50%) translateY(80px);
           background: var(--tinta); color: #fff; font-size: .87rem; font-weight: 600;
           padding: 12px 22px; border-radius: var(--r-full); opacity: 0;
           transition: all .35s cubic-bezier(.34,1.3,.64,1); z-index: 50;
           pointer-events: none; max-width: 90vw; box-shadow: 0 8px 30px rgba(0,0,0,.25); }
  #toast.mostrar { transform: translateX(-50%) translateY(0); opacity: 1; }

  footer { border-top: 1px solid var(--borda-leve); padding: 26px 0 42px;
           text-align: center; color: var(--suave); font-size: .83rem; }"""

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


# Ícones das plataformas em SVG inline — o gradiente do Instagram vem do
# <defs> compartilhado no topo da página (evita ids duplicados por card).
ICONES = {
    "instagram": (
        '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">'
        '<rect x="2.5" y="2.5" width="19" height="19" rx="5.5" '
        'stroke="url(#ig-grad)" stroke-width="2.1"/>'
        '<circle cx="12" cy="12" r="4.3" stroke="url(#ig-grad)" stroke-width="2.1"/>'
        '<circle cx="17.4" cy="6.6" r="1.35" fill="url(#ig-grad)"/></svg>'
    ),
    "tiktok": (
        '<svg viewBox="0 0 24 24" aria-hidden="true">'
        '<path d="M16.4 2.6c.55 1.9 1.95 3.15 3.9 3.35v3.05c-1.5.05-2.9-.35-4.1-1.15v6.25'
        'c0 3.4-2.85 6.05-6.25 5.5-2.6-.42-4.6-2.6-4.7-5.25-.12-3.2 2.45-5.9 5.65-5.8v3.1'
        'c-1.35-.2-2.6.9-2.6 2.3 0 1.3 1.05 2.35 2.35 2.35s2.35-1.05 2.35-2.35V2.6h3.4z" '
        'transform="translate(-.9 -.9)" fill="#25F4EE"/>'
        '<path d="M16.4 2.6c.55 1.9 1.95 3.15 3.9 3.35v3.05c-1.5.05-2.9-.35-4.1-1.15v6.25'
        'c0 3.4-2.85 6.05-6.25 5.5-2.6-.42-4.6-2.6-4.7-5.25-.12-3.2 2.45-5.9 5.65-5.8v3.1'
        'c-1.35-.2-2.6.9-2.6 2.3 0 1.3 1.05 2.35 2.35 2.35s2.35-1.05 2.35-2.35V2.6h3.4z" '
        'transform="translate(.9 .9)" fill="#FE2C55"/>'
        '<path d="M16.4 2.6c.55 1.9 1.95 3.15 3.9 3.35v3.05c-1.5.05-2.9-.35-4.1-1.15v6.25'
        'c0 3.4-2.85 6.05-6.25 5.5-2.6-.42-4.6-2.6-4.7-5.25-.12-3.2 2.45-5.9 5.65-5.8v3.1'
        'c-1.35-.2-2.6.9-2.6 2.3 0 1.3 1.05 2.35 2.35 2.35s2.35-1.05 2.35-2.35V2.6h3.4z" '
        'fill="#161823"/></svg>'
    ),
    "youtube": (
        '<svg viewBox="0 0 24 24" aria-hidden="true">'
        '<rect x="1.5" y="4.5" width="21" height="15" rx="4.5" fill="#FF0000"/>'
        '<path d="M10 8.6l6 3.4-6 3.4V8.6z" fill="#fff"/></svg>'
    ),
}

DEFS_SVG = (
    '<svg width="0" height="0" aria-hidden="true" style="position:absolute"><defs>'
    '<linearGradient id="ig-grad" x1="0%" y1="100%" x2="100%" y2="0%">'
    '<stop offset="0%" stop-color="#FCAF45"/><stop offset="25%" stop-color="#F77737"/>'
    '<stop offset="50%" stop-color="#E1306C"/><stop offset="75%" stop-color="#C13584"/>'
    '<stop offset="100%" stop-color="#833AB4"/></linearGradient></defs></svg>'
)


def _chip_plataforma(origem: str) -> str:
    """Chip da plataforma de origem usando o logo em vez do nome."""
    o = (origem or "").lower()
    if not o:
        return ""
    nomes = [n for n in ("instagram", "tiktok", "youtube") if n in o]
    if not nomes:
        nomes = ["instagram", "tiktok"] if "multi" in o else []
    if not nomes:
        return ""
    icones = "".join(ICONES[n] for n in nomes)
    return (f'<span class="chip plataforma" title="Tendência: {escape(origem)}">'
            f'{icones}</span>')


def _icone_por_url(url: str) -> str:
    """Logo da plataforma deduzido do domínio do link do viral."""
    u = (url or "").lower()
    for nome in ("instagram", "tiktok", "youtube"):
        if nome in u:
            return ICONES[nome]
    return ""


def _valor_metrica(metrica: str) -> float:
    """Interpreta '27.7M views' / '120k' / '15 mil' como valor numérico."""
    sufixos = {"m": 1_000_000, "mi": 1_000_000, "k": 1_000, "mil": 1_000}
    valores = [
        float(n.replace(",", ".")) * sufixos.get((s or "").strip(), 1)
        for n, s in re.findall(r"(\d+(?:[.,]\d+)?)\s*(m\b|mi\b|k\b|mil\b)?", metrica.lower())
    ]
    return max(valores, default=0.0)


def _resumo_metrica(ideia: dict) -> str:
    """A métrica da âncora mais forte, resumida para o card compacto
    (ex.: '27.7M views, 8.8% engajamento' -> '27.7M views')."""
    metricas = [v.get("metrica", "").split(",")[0].strip()
                for v in ideia.get("virais_origem", []) if v.get("metrica")]
    return max(metricas, key=_valor_metrica, default="")


def _cartao(ideia: dict, posicao: int) -> str:
    dia, hora = slot_para(posicao)
    chip_dia = f"{escape(dia)} · {escape(hora)}" if hora else escape(dia)
    origem = ideia.get("plataforma_origem_da_tendencia", "")
    metrica_resumo = _resumo_metrica(ideia)
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
               f'<span class="logo">{_icone_por_url(v["url"])}</span>'
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
        {f'<span class="chip views">🔥 {escape(metrica_resumo)}</span>' if metrica_resumo else ''}
        {_chip_plataforma(origem)}
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
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{ESTILO}</style>
</head>
<body>
{DEFS_SVG}
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
