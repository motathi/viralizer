"""Publica todas as agendas como uma página só (web/index.html).

A página reúne, numa lista única, as ideias de todas as semanas já geradas
mais as que saíram do estúdio — sem galeria à parte e sem separar por
semana. Cada card traz de que semana veio.

O que a página faz:
- cards compactos em grade que expandem ao clicar;
- alternância Reels ⇄ Carrossel e escolha entre as 3 opções de gancho
  (o gancho escolhido substitui o bloco de abertura do roteiro);
- fila de produção: "minha lista" → "feita", com filtros e contador;
- descarte individual (✕) com restauração;
- copiar roteiro e link compartilhável de um roteiro só (#r<id>).

As gerações passadas vêm de src/publicar/arquivo.py; o estilo, a navegação
e o JavaScript comuns de src/publicar/base.py; as demais páginas de
src/publicar/paginas.py.
"""

import re
from datetime import date, timedelta
from html import escape
from pathlib import Path

from src.agenda.montador import normalizar_ideia
from src.publicar.arquivo import registrar as registrar_agenda, semear_de_paginas
from src.publicar.base import documento
from src.publicar.paginas import galeria_publicada
from src.publicar.paginas import publicar_paginas

ESTILO_AGENDA = """
  #banner-foco { display: none; border-radius: var(--r-md); padding: 14px 18px;
                 margin: 18px 0 0; font-size: .9rem; align-items: center;
                 justify-content: space-between; gap: 10px; flex-wrap: wrap;
                 background: var(--grad-suave); border: 1px solid var(--borda-leve); }
  body.em-foco #banner-foco { display: flex; }
  body.em-foco .painel, body.em-foco .aviso { display: none; }
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
  .descartar { position: absolute; right: 44px; top: 16px; width: 24px; height: 24px;
               border: 0; background: transparent; color: var(--borda); font-size: 1rem;
               line-height: 1; cursor: pointer; border-radius: 50%; transition: all .2s; }
  .descartar:hover { background: #fdeef2; color: var(--ig-pink); }
  .cartao.descartada { display: none; }
  .chip.plataforma { display: inline-flex; align-items: center; gap: 5px;
                     padding: 4px 10px; background: var(--fundo);
                     border: 1px solid var(--borda-leve); }
  .chip.plataforma svg { width: 15px; height: 15px; display: block; }
  .viral-item .logo { width: 14px; height: 14px; vertical-align: -2px;
                      margin-right: 5px; display: inline-block; }
  .chip.semana { font-variant-numeric: tabular-nums; }
  .chip.minha { background: var(--grad-suave); border-color: transparent; color: var(--acento); font-weight: 700; }
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
  .virais-origem { display: flex; flex-direction: column; gap: 8px; }
  .viral-item { background: var(--superficie); border-radius: var(--r-md);
                padding: 11px 15px; font-size: .86rem;
                border: 1px solid var(--borda-leve);
                border-left: 3px solid var(--ig-magenta); }
  .viral-item a { color: var(--ig-magenta); font-weight: 700; text-decoration: none; }
  .viral-item a:hover { text-decoration: underline; }
  .viral-item .metrica { color: var(--ok); font-weight: 700; }
  .viral-item .motivo { color: var(--suave); display: block; margin-top: 2px; }
  .viral-item .fala { display: block; margin-top: 4px; padding-left: 9px;
    border-left: 2px solid var(--borda); color: var(--tinta); font-style: italic; }
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
  .btn.na-lista-btn { background: var(--grad-suave); border: 1.5px solid transparent;
                      background-origin: border-box; color: var(--ig-magenta); }
  .btn.feito-btn.marcado { background: var(--ok-claro); border-color: var(--ok); color: var(--ok); }

  .vazio { text-align: center; color: var(--suave); padding: 44px 0; display: none; }
"""

SCRIPT = r"""
const DADOS = JSON.parse(document.getElementById('dados-agenda').textContent);
const IDEIAS = {};
DADOS.ideias.forEach(d => { IDEIAS[d.id] = d; });

// O estado é um só para todas as semanas: uma ideia descartada some da
// lista inteira, não só da semana em que nasceu.
const estado = Radar.estadoAgenda(DADOS.nicho);
const abertas = new Set();
let filtro = 'todas';
let foco = null;

function st(id) {
  return estado[id] || (estado[id] = {lista: false, feito: false, descartada: false,
                                      formato: 'reels', gancho: 0});
}
function salvar() {
  Radar.gravarEstadoAgenda(DADOS.nicho, estado);
  registrarEscolhas();
}
let aviso = null;
// As escolhas viram sinal de gosto para o estúdio; no painel, também vão
// para o arquivo de feedback do nicho.
function registrarEscolhas() {
  if (!DADOS.nicho) return;
  clearTimeout(aviso);
  aviso = setTimeout(() => {
    const ideias = DADOS.ideias.map(d => {
      const s = st(d.id);
      return {titulo: d.titulo, pilar: d.pilar, registro: d.registro,
              estado: s.feito ? 'feita' : s.descartada ? 'descartada' : s.lista ? 'lista' : 'nenhum'};
    });
    Radar.registrarFeedback(DADOS.nicho, 'todas', ideias);
    // No painel, as escolhas também vão para o arquivo de feedback do nicho.
    // Quem responde /api/ia diz se é o painel — adivinhar pelo endereço
    // erra em túnel, preview e servidor local qualquer.
    Radar.estadoIA().then(estado => {
      if (!estado.painel) return;
      fetch('/feedback', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({nicho: DADOS.nicho, semana: 'todas', ideias})}).catch(() => {});
    }).catch(() => {});
  }, 400);
}
const toast = Radar.toast;
const copiar = Radar.copiar;
const escapar = Radar.escapar;

function lerHash() {
  const m = location.hash.match(/^#r(.+)$/);
  foco = (m && document.getElementById('r' + m[1])) ? m[1] : null;
  if (foco !== null) abertas.add(foco);
  document.body.classList.toggle('em-foco', foco !== null);
}

// ── as ideias criadas no estúdio entram na mesma lista ────────────────
function cartaoMinhaIdeia(item) {
  const r = item.roteiro || {};
  const blocos = (r.blocos || []).map(b => `<div class="bloco-tempo">
    <span class="tempo">${escapar(b.rotulo)}</span>
    <div><div>${escapar(b.texto)}</div>${b.direcao ? `<div class="direcao">${escapar(b.direcao)}</div>` : ''}</div></div>`).join('');
  const rotulos = {video: '🎬 Vídeo', carrossel: '🖼️ Carrossel', stories: '📱 Stories'};
  const publicada = item.origem === 'site';
  return `<article class="cartao minha${publicada ? ' publicada' : ''}" data-id="${escapar(item.id)}" id="r${escapar(item.id)}">
    <div class="cab">
      <button class="descartar" title="Apagar esta ideia" aria-label="Apagar">✕</button>
      <span class="seta">▼</span>
      <div class="topo">
        <span class="chip minha">✨ sua ideia</span>
        <span class="chip">${rotulos[item.formato] || escapar(item.formato || '')}</span>
        ${item.tom ? `<span class="chip">${escapar(item.tom)}</span>` : ''}
        <span class="chip chip-status lista">📌 na lista</span>
        <span class="chip chip-status feito">✓ feita</span>
      </div>
      <h3>${escapar(r.titulo || item.ideia)}</h3>
      <p class="previa"></p>
    </div>
    <div class="detalhe">
      ${r.gancho ? `<div class="rotulo">Gancho</div><p class="gancho-gal">🪝 ${escapar(r.gancho)}</p>` : ''}
      <div class="rotulo">Roteiro</div>${blocos}
      ${r.legenda ? `<div class="rotulo">Legenda pronta</div><div class="legenda">${escapar(r.legenda)}</div>` : ''}
      <div class="hashtags">${(r.hashtags || []).map(escapar).join(' ')}</div>
      <p class="previa" style="font-style:normal;margin-top:12px">Ideia original: ${escapar(item.ideia || '')}</p>
      <div class="acoes">
        <button class="btn primario na-lista-btn2">+ Adicionar à lista</button>
        <button class="btn feito-btn">Marcar como feita</button>
        <button class="btn copiar-btn">📋 Copiar roteiro</button>
        <a class="btn" href="estudio.html?id=${encodeURIComponent(item.id)}">✏️ Reabrir no estúdio</a>
      </div>
    </div>
  </article>`;
}
function minhasIdeias() { return Radar.minhasIdeias(DADOS.nicho, DADOS.minhas_publicadas); }
function montarMinhas() {
  const lista = document.getElementById('lista-cartoes');
  lista.querySelectorAll('.cartao.minha').forEach(c => c.remove());
  const itens = minhasIdeias();
  if (!itens.length) return;
  lista.insertAdjacentHTML('afterbegin', itens.map(cartaoMinhaIdeia).join(''));
}

function render() {
  let naLista = 0, feitas = 0, visiveis = 0, descartadas = 0;
  document.querySelectorAll('.cartao').forEach(c => {
    const id = c.dataset.id, s = st(id), d = IDEIAS[id];
    const minha = c.classList.contains('minha');
    if (s.descartada) descartadas++;
    if (s.lista && !s.feito && !s.descartada) naLista++;
    if (s.feito && !s.descartada) feitas++;
    c.classList.toggle('descartada', !!s.descartada);
    c.classList.toggle('feita', s.feito);
    c.classList.toggle('na-lista', s.lista);
    c.classList.toggle('aberta', abertas.has(id));
    const btnL = c.querySelector('.na-lista-btn2');
    btnL.classList.toggle('na-lista-btn', s.lista);
    btnL.textContent = s.lista ? '✓ Na minha lista' : '+ Adicionar à lista';
    const btnF = c.querySelector('.feito-btn');
    btnF.classList.toggle('marcado', s.feito);
    btnF.textContent = s.feito ? '✓ Feita!' : 'Marcar como feita';
    if (d) {
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
    }
    // "Minha lista" = fila de produção: o que foi feito sai dela e vai para "Feitas"
    const passaFiltro = filtro === 'todas' ? !s.descartada
      : filtro === 'minhas' ? (minha && !s.descartada)
      : filtro === 'lista' ? (s.lista && !s.feito && !s.descartada)
      : (s.feito && !s.descartada);
    const mostra = foco !== null ? id === foco : passaFiltro;
    c.classList.toggle('oculta', !mostra);
    if (mostra) visiveis++;
  });
  document.getElementById('contagem').innerHTML =
    `<b>${naLista}</b> na fila · <b>${feitas}</b> feita${feitas === 1 ? '' : 's'}`;
  const barra = document.getElementById('barra-descartadas');
  barra.classList.toggle('visivel', descartadas > 0);
  barra.querySelector('span').textContent =
    `${descartadas} ideia${descartadas === 1 ? '' : 's'} descartada${descartadas === 1 ? '' : 's'}`;
  document.querySelectorAll('.aba').forEach(a => a.classList.toggle('ativa', a.dataset.filtro === filtro));
  document.getElementById('vazio').style.display = visiveis ? 'none' : 'block';
  salvar();
}

function textoRoteiro(id) {
  const d = IDEIAS[id];
  if (!d) {
    const item = minhasIdeias().find(i => i.id === id);
    return item ? Radar.textoRoteiro(item.roteiro || {}) : '';
  }
  const s = st(id);
  const gancho = d.ganchos[s.gancho] || d.ganchos[0];
  let out = d.titulo + '\n\n🎣 Gancho: ' + gancho + '\n\n';
  if (s.formato === 'reels' || !d.carrossel.laminas.length) {
    out += '🎬 ROTEIRO (Reels/TikTok)\n';
    d.reels.forEach((b, i) => {
      out += `\n[${b.tempo}] ${i === 0 ? gancho : b.fala}`;
      if (b.direcao) out += `\n   🎥 ${b.direcao}`;
    });
  } else {
    out += '🖼️ CARROSSEL\nCapa: ' + d.carrossel.capa;
    d.carrossel.laminas.forEach((l, i) => { out += `\nLâmina ${i + 1}: ${l}`; });
    out += '\nCTA final: ' + d.carrossel.cta_final;
  }
  out += '\n\n✍️ Legenda:\n' + d.legenda + '\n\n' + d.hashtags.join(' ');
  return out;
}

document.getElementById('restaurar').addEventListener('click', () => {
  Object.values(estado).forEach(e => { e.descartada = false; });
  toast('Ideias restauradas');
  render();
});

// Aviso quando a agenda mais recente não é atualizada há mais de 8 dias
(function avisarSeAntiga() {
  const dias = Math.floor((Date.now() - new Date(DADOS.gerado_em + 'T12:00:00')) / 86400000);
  if (dias > 8) {
    const el = document.getElementById('aviso-antiga');
    el.querySelector('span').textContent =
      `⚠️ A agenda mais recente foi gerada há ${dias} dias — a atualização automática de segunda pode ter falhado.`;
    el.classList.add('visivel');
  }
})();

document.getElementById('sair-foco').addEventListener('click', () => {
  history.replaceState(null, '', location.pathname);
  lerHash(); render();
});
window.addEventListener('hashchange', () => { lerHash(); render(); });

document.addEventListener('click', e => {
  const aba = e.target.closest('.aba');
  // trocar de aba sempre volta para os cards reduzidos
  if (aba) { filtro = aba.dataset.filtro; abertas.clear(); render(); return; }
  const c = e.target.closest('.cartao');
  if (!c) return;
  const id = c.dataset.id, s = st(id);
  if (e.target.closest('.descartar')) {
    if (c.classList.contains('minha') && !c.classList.contains('publicada')) {
      if (!confirm('Apagar esta ideia?')) return;
      Radar.apagarMinhaIdeia(DADOS.nicho, id);
      delete estado[id];
      c.remove(); toast('Ideia apagada'); render(); return;
    }
    s.descartada = true; abertas.delete(id);
    toast('Ideia descartada — dá pra restaurar no topo');
  } else if (e.target.closest('.cab')) {
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
    copiar(location.origin + location.pathname + '#r' + id, 'Link do roteiro copiado 🔗'); return;
  } else { return; }
  render();
});

montarMinhas();
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


def _rotulo_semana(semana: str) -> str:
    """"2026-09-14" -> "14/09" — o card diz de que semana a ideia veio."""
    try:
        a, m, d = semana.split("-")
        return f"📅 {d}/{m}"
    except ValueError:
        return "📅"


def _cartao(ideia: dict, ident: str, semana: str) -> str:
    origem = ideia.get("plataforma_origem_da_tendencia", "")
    metrica_resumo = _resumo_metrica(ideia)
    carrossel = ideia["roteiro_carrossel"]

    ganchos = "".join(
        f'<label class="gancho-opcao"><input type="radio" name="g{ident}">'
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

    nota = ideia.get("conformidade_cfm", "")
    nota_extra = (f'<details><summary>📝 Observação</summary>'
                  f'<p class="texto">{escape(nota)}</p></details>' if nota else "")

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
            + (f'<span class="fala">“{escape(v["fala_literal"])}”</span>'
               if v.get("fala_literal") else "")
            + "</div>"
            for v in ideia["virais_origem"]
        )
        padrao = (f'<div class="padrao">🧩 <b>Padrão aplicado:</b> '
                  f'{escape(ideia["padrao_aplicado"])}</div>'
                  if ideia.get("padrao_aplicado") else "")
        voz = ideia.get("voz") or {}
        voz_html = (f'<div class="padrao">🗣️ <b>Voz deste roteiro:</b> '
                    f'{escape(voz["registro"])}'
                    + (f' — {escape(voz["de_onde_veio"])}'
                       if voz.get("de_onde_veio") else "")
                    + '</div>') if voz.get("registro") else ""
        virais_html = (
            '<div class="rotulo">🎯 Virais que inspiraram esta ideia</div>'
            f'<div class="virais-origem">{itens}</div>{padrao}{voz_html}'
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
  <article class="cartao" data-id="{ident}" id="r{ident}">
    <div class="cab">
      <button class="descartar" title="Descartar esta ideia" aria-label="Descartar">✕</button>
      <span class="seta">▼</span>
      <div class="topo">
        <span class="chip semana">{_rotulo_semana(semana)}</span>
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
      {nota_extra}

      <div class="acoes">
        <button class="btn primario na-lista-btn2">+ Adicionar à lista</button>
        <button class="btn feito-btn">Marcar como feita</button>
        <button class="btn copiar-btn">📋 Copiar roteiro</button>
        <button class="btn compartilhar-btn">🔗 Compartilhar</button>
      </div>
    </div>
  </article>"""


def semana_seguinte(hoje: date | None = None) -> str:
    """A segunda-feira que a agenda cobre (ISO)."""
    hoje = hoje or date.today()
    return (hoje + timedelta(days=(7 - hoje.weekday()) % 7 or 7)).isoformat()


def publicar_site(config: dict, agendas: list[dict], destino: Path,
                  nicho: str | None = None, total_sinais: int = 0,
                  raiz_dados: Path | None = None) -> None:
    """Escreve web/index.html com as ideias de todas as semanas guardadas.

    `agendas` vem de src/publicar/arquivo.py, da mais recente para a mais
    antiga; cada uma traz `semana`, `gerado_em` e `ideias` já normalizadas.
    """
    cartoes, catalogo = [], []
    for agenda in agendas:
        semana = agenda.get("semana", "")
        for i, bruta in enumerate(agenda.get("ideias") or []):
            ideia = normalizar_ideia(bruta)
            ident = f"g{semana}-{i}"
            cartoes.append(_cartao(ideia, ident, semana))
            catalogo.append({
                "id": ident, "semana": semana,
                "titulo": ideia["titulo"], "pilar": ideia.get("pilar", ""),
                "registro": (ideia.get("voz") or {}).get("registro", ""),
                "ganchos": [g for g in ideia["ganchos_3s"] if g],
                "reels": ideia["roteiro_reels"], "carrossel": ideia["roteiro_carrossel"],
                "legenda": ideia.get("legenda_post") or ideia.get("cta", ""),
                "hashtags": ideia.get("hashtags", []),
            })

    recente = agendas[0] if agendas else {}
    gerado_em = recente.get("gerado_em") or date.today().isoformat()
    dados = {"nicho": nicho or "", "gerado_em": gerado_em,
             "semanas": [a.get("semana", "") for a in agendas], "ideias": catalogo,
             "minhas_publicadas": galeria_publicada(raiz_dados, nicho) if (raiz_dados and nicho) else []}

    corpo = f"""
<header class="hero container">
  <div class="selo">Agenda de conteúdo</div>
  <h1>Todas as ideias — <span>{escape(config['nome'])}</span></h1>
  <p class="sub">{len(catalogo)} ideias de {len(agendas)} semana{'s' if len(agendas) != 1 else ''}, mais o que você criar no
  <a href="estudio.html">estúdio</a> · atualizada em {date.fromisoformat(gerado_em).strftime('%d/%m/%Y')}</p>
</header>

<div class="painel">
  <div class="container painel-linha">
    <div class="abas">
      <button class="aba ativa" data-filtro="todas">Todas</button>
      <button class="aba" data-filtro="minhas">✨ Minhas ideias</button>
      <button class="aba" data-filtro="lista">📌 Minha lista</button>
      <button class="aba" data-filtro="feitas">✓ Feitas</button>
    </div>
    <div class="progresso" id="contagem"></div>
    <div class="semanas"><a class="btn" href="estudio.html">✨ Criar uma ideia</a></div>
  </div>
</div>

<section class="agenda container">
  <div id="banner-foco">
    <span>🔗 Você está vendo um roteiro compartilhado.</span>
    <button class="btn" id="sair-foco">Ver a agenda completa</button>
  </div>
  <div class="banner-aviso alerta" id="aviso-antiga"><span></span></div>
  <div class="banner-aviso neutro" id="barra-descartadas"><span></span>
    <button class="btn" id="restaurar">Restaurar descartadas</button></div>
  <div class="aviso">⚕️ Todo conteúdo é um rascunho embasado: a palavra final sobre
  qualquer afirmação médica é sempre da profissional. Toque em um card para abrir o roteiro.</div>
  <div class="lista-cartoes" id="lista-cartoes">{''.join(cartoes)}</div>
  <p class="vazio" id="vazio">Nada por aqui ainda. 📌</p>
</section>
"""
    html = documento(titulo=f"Agenda de conteúdo — {config['nome']}", ativa="agenda",
                     corpo=corpo, estilo_extra=ESTILO_AGENDA, script=SCRIPT, dados=dados,
                     id_dados="dados-agenda")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")


def publicar_agenda(config: dict, roteiros: dict, sinais: dict, raiz: Path,
                    nicho: str | None = None, semana: str | None = None,
                    gerado_em: str | None = None) -> Path:
    """Guarda a geração desta semana e reescreve o site com tudo o que existe.

    Não há mais uma página por semana: as ideias de todas elas ficam na
    mesma lista em web/index.html. As páginas de ferramentas (estúdio,
    manual, ferramentas) são reescritas junto.
    """
    web = raiz / "web"
    web.mkdir(parents=True, exist_ok=True)
    semana = semana or semana_seguinte()
    gerado_em = gerado_em or date.today().isoformat()

    if nicho:
        semear_de_paginas(raiz, nicho)  # traz as semanas que só existiam como HTML
        ideias = [normalizar_ideia(i) for i in roteiros["ideias"]]
        agendas = registrar_agenda(raiz, nicho, semana, gerado_em, ideias)
    else:
        agendas = [{"semana": semana, "gerado_em": gerado_em,
                    "ideias": [normalizar_ideia(i) for i in roteiros["ideias"]]}]

    publicar_site(config, agendas, web / "index.html", nicho=nicho, raiz_dados=raiz,
                  total_sinais=sum(len(v) for v in sinais.values()))
    if nicho:
        publicar_paginas(config, raiz, nicho)
    return web / "index.html"
