"""As páginas de ferramentas do site publicado: estúdio, manual e
ferramentas. A galeria deixou de existir à parte — o que sai do estúdio
entra na própria agenda.

Tudo aqui roda no navegador de quem abre o site, sem depender do
computador onde o painel foi instalado. O estúdio fala com a IA por
/api/ia, onde a chave da Anthropic fica no servidor — uma só para todo
mundo que abre o site (ver api/ia.js).
"""

import json
import subprocess
from datetime import date
from html import escape
from pathlib import Path

from src import feedback as feedback_mod
from src.descoberta import termos as termos_mod
from src.painel import estudio as estudio_mod
from src.publicar.base import documento
from src.roteiros import manual as manual_mod
from src.roteiros.gerador import MODELO_ESCRITA, MODELO_PESQUISA

MAX_TOKENS_ESTUDIO = 16000


# ── dados que as páginas levam embutidos ─────────────────────────────────

def galeria_publicada(raiz: Path, nicho: str) -> list[dict]:
    arquivo = raiz / "dados" / f"galeria-{nicho}.json"
    if not arquivo.exists():
        return []
    try:
        itens = json.loads(arquivo.read_text(encoding="utf-8")).get("itens", [])
    except (ValueError, OSError):
        return []
    return sorted(itens, key=lambda i: i.get("atualizado_em", ""), reverse=True)


def _url_repositorio(raiz: Path) -> str:
    """Endereço público do repositório (para o link do GitHub Actions)."""
    try:
        r = subprocess.run(["git", "config", "--get", "remote.origin.url"], cwd=raiz,
                           capture_output=True, text=True, timeout=5, check=False)
        url = r.stdout.strip()
    except Exception:  # noqa: BLE001 - sem git, sem link
        return ""
    if url.startswith("git@github.com:"):
        url = "https://github.com/" + url[len("git@github.com:"):]
    if url.endswith(".git"):
        url = url[:-4]
    return url if url.startswith("https://github.com/") else ""


def _contexto_estudio(config: dict, raiz: Path, nicho: str) -> dict:
    ctx = {"nicho": config["nome"], "perfil": config.get("perfil", {}),
           "preferencias_do_perfil": config.get("preferencias", [])}
    manual = manual_mod.carregar(raiz, nicho)
    if manual:
        ctx["manual_do_nicho"] = manual_mod.para_prompt(manual)
    prefs = feedback_mod.preferencias(raiz, nicho)
    if prefs:
        ctx["preferencias_reveladas"] = prefs
    return ctx


# ── Estúdio ──────────────────────────────────────────────────────────────

ESTILO_ESTUDIO = """
  .etapas { display: flex; gap: 8px; margin: 0 0 22px; flex-wrap: wrap; justify-content: center; }
  .etapa { font-size: .78rem; font-weight: 600; color: var(--suave); padding: 6px 12px;
           border-radius: var(--r-full); border: 1px solid var(--borda-leve); }
  .etapa.ativa { color: #fff; background: var(--grad); border-color: transparent; }
  .cartao-estudio { border: 1px solid var(--borda); border-radius: var(--r-lg); padding: 20px; background: var(--fundo);
                    box-shadow: var(--sombra-1); }
  .form { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .form .larga { grid-column: 1 / -1; }
  .form-acoes { display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap; align-items: center; font-size: .88rem; color: var(--suave); }
  .opcoes { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
  .opcao { display: flex; flex-direction: column; }
  .opcao .chip { align-self: flex-start; }
  .opcao h3 { font-size: 1rem; margin: 8px 0 4px; }
  .opcao .angulo { color: var(--suave); font-size: .86rem; margin-bottom: 10px; }
  .opcao .previa { flex: 1; max-height: 340px; overflow: auto; padding-right: 4px; }
  .opcao .por-que { font-size: .82rem; color: var(--suave); margin: 10px 0; }
  .editor { display: grid; grid-template-columns: 1.2fr .8fr; gap: 16px; align-items: start; }
  .chat { display: flex; flex-direction: column; max-height: 78vh; }
  .mensagens { flex: 1; overflow: auto; display: flex; flex-direction: column; gap: 10px; padding: 4px 2px 12px; }
  .msg { max-width: 92%; padding: 10px 14px; border-radius: 16px; font-size: .92rem; white-space: pre-wrap; }
  .msg.eu { align-self: flex-end; background: var(--grad); color: #fff; border-bottom-right-radius: 4px; }
  .msg.ia { align-self: flex-start; background: var(--superficie); border: 1px solid var(--borda-leve); border-bottom-left-radius: 4px; }
  .entrada { display: flex; gap: 8px; border-top: 1px solid var(--borda-leve); padding-top: 12px; }
  .entrada input { flex: 1; }
  .sugestoes { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
  .sugestoes .btn { font-size: .78rem; padding: 6px 11px; font-weight: 600; }
  .titulo-roteiro { margin: 10px 0 4px; font-size: 1.05rem; }
  .angulo-roteiro { color: var(--suave); font-size: .86rem; margin-bottom: 12px; }
  section.estudio { padding: 0 0 60px; }
  @media (max-width: 820px) {
    .form, .opcoes, .editor { grid-template-columns: 1fr; }
    .opcao .previa { max-height: none; }
    .chat { max-height: none; }
  }
"""

CORPO_ESTUDIO = """
<header class="hero container">
  <div class="selo">Estúdio de roteiros</div>
  <h1>Sua ideia, <span>três roteiros</span></h1>
  <p class="sub">Você dá a ideia e escolhe formato, estilo e tom. A IA escreve três opções em ângulos
  diferentes; você escolhe uma, ajusta conversando e salva — a ideia entra na agenda junto com as outras.
  Não precisa configurar nada.</p>
</header>
<section class="estudio container">
  <div class="banner-aviso alerta" id="aviso-chave"><span id="aviso-chave-texto"></span>
    <a class="btn" href="ferramentas.html#chave">Ver o estado da IA</a></div>

  <div class="etapas">
    <span class="etapa ativa" id="et1">1 · Ideia e formato</span>
    <span class="etapa" id="et2">2 · Escolha uma opção</span>
    <span class="etapa" id="et3">3 · Ajuste e salve</span>
  </div>

  <section id="passo1" class="cartao-estudio">
    <div class="form">
      <div class="larga"><label class="campo" for="ideia">Sua ideia</label>
        <textarea id="ideia" placeholder="Ex.: explicar por que protetor solar dentro de casa faz diferença, usando a luz da janela do consultório como prova"></textarea></div>
      <div><label class="campo" for="formato">Formato</label><select id="formato"></select></div>
      <div><label class="campo" for="tamanho">Tamanho</label><select id="tamanho"></select></div>
      <div><label class="campo" for="estilo">Estilo</label><select id="estilo"></select></div>
      <div><label class="campo" for="tom">Tom</label><select id="tom"></select></div>
      <div class="larga"><label class="campo" for="obs">Observações (opcional)</label>
        <input type="text" id="obs" placeholder="Ex.: mencionar que atendo em Curitiba; não usar a palavra 'milagre'"></div>
    </div>
    <div class="form-acoes">
      <button class="btn primario" id="gerar">Escrever 3 opções</button>
      <span id="estado1"></span>
    </div>
    <div class="mensagem erro" id="erro1" hidden></div>
  </section>

  <section id="passo2" hidden>
    <div class="titulo-secao">Três ângulos para a mesma ideia — escolha um</div>
    <div class="opcoes" id="opcoes"></div>
    <div class="form-acoes"><button class="btn" id="voltar1">← Mudar a ideia ou os parâmetros</button></div>
  </section>

  <section id="passo3" hidden>
    <div class="editor">
      <div class="cartao-estudio" id="roteiro"></div>
      <div class="cartao-estudio chat">
        <div class="titulo-secao">Ajuste conversando</div>
        <div class="sugestoes" id="sugestoes"></div>
        <div class="mensagens" id="mensagens"></div>
        <div class="entrada">
          <input type="text" id="pedido" placeholder="Ex.: deixa o gancho mais provocador" aria-label="O que mudar">
          <button class="btn primario" id="enviar">Enviar</button>
        </div>
        <div class="mensagem erro" id="erro3" hidden></div>
        <div class="acoes">
          <button class="btn primario" id="salvar">💾 Salvar na agenda</button>
          <button class="btn" id="copiar">📋 Copiar</button>
          <button class="btn" id="voltar2">← Ver as 3 opções</button>
        </div>
        <div class="mensagem ok" id="salvo" hidden></div>
      </div>
    </div>
  </section>
</section>
"""

SCRIPT_ESTUDIO = r"""
const CFG = JSON.parse(document.getElementById('dados-pagina').textContent);
const $ = s => document.querySelector(s);
const escapar = Radar.escapar;
let opcoes = [], roteiro = null, conversa = [], idSalvo = null, params = {};

async function conferirIA(recarregar) {
  const estado = await Radar.estadoIA(recarregar);
  const pronta = estado.configurada || !!Radar.chave();
  $('#aviso-chave').classList.toggle('visivel', !pronta);
  $('#aviso-chave-texto').textContent = estado.servidor
    ? '🔑 O site ainda não tem uma chave da Anthropic configurada — sem ela o estúdio não escreve.'
    : '🔑 Esta página não está ligada ao servidor da IA. Abra pelo site publicado ou pelo painel.';
}
function contexto() {
  const ctx = {...CFG.contexto};
  const prefs = Radar.preferencias(CFG.nicho);
  if (prefs) ctx.preferencias_reveladas = prefs;
  return ctx;
}
function etapa(n) {
  [1, 2, 3].forEach(i => { $('#et' + i).classList.toggle('ativa', i === n); $('#passo' + i).hidden = i !== n; });
  window.scrollTo({top: 0, behavior: 'smooth'});
}
function montarMenus() {
  const opt = (lista, rot) => lista.map(v => `<option value="${escapar(v)}">${escapar(rot ? rot(v) : v)}</option>`).join('');
  $('#formato').innerHTML = opt(Object.keys(CFG.menus.formatos), k => CFG.menus.formatos[k]);
  $('#estilo').innerHTML = opt(CFG.menus.estilos);
  $('#tom').innerHTML = opt(CFG.menus.tons);
  atualizarTamanhos();
  $('#formato').onchange = atualizarTamanhos;
}
function atualizarTamanhos() {
  const f = $('#formato').value;
  $('#tamanho').innerHTML = (CFG.menus.tamanhos[f] || []).map(v => `<option>${escapar(v)}</option>`).join('');
  if (f === 'video') $('#tamanho').value = '45s';
}
function lerParams() {
  params = {nicho: CFG.nicho, ideia: $('#ideia').value.trim(), formato: $('#formato').value,
            tamanho: $('#tamanho').value, estilo: $('#estilo').value, tom: $('#tom').value,
            observacoes: $('#obs').value.trim().slice(0, 800)};
  return params;
}
function mostrarErro(sel, e) {
  const el = $(sel);
  const link = (e.semChave || e.pedeSenha) ? ' <a href="ferramentas.html#chave">Ver o estado da IA</a>' : '';
  el.innerHTML = '⚠️ ' + escapar(e.message || e) + link;
  el.hidden = false;
}

$('#gerar').onclick = async () => {
  lerParams();
  $('#erro1').hidden = true;
  if (params.ideia.length < 5) { mostrarErro('#erro1', new Error('Escreva a ideia com um pouco mais de detalhe.')); return; }
  $('#gerar').disabled = true;
  const estado = $('#estado1');
  estado.innerHTML = '<span class="girando"></span>Escrevendo três opções — leva por volta de um minuto…';
  try {
    const conteudo = {...contexto(), pedido: {ideia: params.ideia, formato: params.formato, estilo: params.estilo,
                      tom: params.tom, tamanho: params.tamanho, observacoes: params.observacoes}};
    const texto = await Radar.chamarIA({modelo: CFG.modelo, maxTokens: CFG.max_tokens, thinking: {type: 'adaptive'},
      system: CFG.prompts.opcoes,
      messages: [{role: 'user', content: JSON.stringify(conteudo, null, 2)}],
      aoProgresso: n => { estado.innerHTML = `<span class="girando"></span>Escrevendo… ${Math.round(n / 1000)} mil caracteres`; }});
    const lista = (Radar.extrairJson(texto).opcoes || []).filter(o => o && typeof o === 'object').map(Radar.limparRoteiro);
    if (!lista.length) throw new Error('A IA não devolveu opções. Tente de novo.');
    opcoes = lista.slice(0, 3); idSalvo = null;
    mostrarOpcoes();
  } catch (e) { mostrarErro('#erro1', e); }
  $('#gerar').disabled = false; estado.textContent = '';
};
function mostrarOpcoes() {
  $('#opcoes').innerHTML = opcoes.map((o, i) => `<div class="cartao-estudio opcao">
    <span class="chip">Opção ${i + 1}</span><h3>${escapar(o.titulo)}</h3><p class="angulo">${escapar(o.angulo)}</p>
    <div class="previa">${Radar.roteiroHtml(o, false)}</div>
    <p class="por-que">📈 ${escapar(o.por_que_funciona)}</p>
    <button class="btn primario" data-i="${i}">Escolher esta</button></div>`).join('');
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
  $('#roteiro').innerHTML = `<span class="chip">${escapar(CFG.menus.formatos[params.formato] || params.formato)}</span>
    <span class="chip">${escapar(params.tom || '')}</span> <span class="chip">${escapar(params.tamanho || '')}</span>
    <h3 class="titulo-roteiro">${escapar(roteiro.titulo)}</h3><p class="angulo-roteiro">${escapar(roteiro.angulo)}</p>
    ${Radar.roteiroHtml(roteiro, true)}`;
  const sug = {video: ['Gancho mais provocador', 'Encurta pra 30s', 'Menos técnico', 'Fecha com pergunta'],
               carrossel: ['Capa mais curta', 'Uma lâmina a menos', 'Menos texto por lâmina', 'CTA pra salvar'],
               stories: ['Põe uma enquete no 2º', 'Primeiro story mais forte', 'Mais bastidor', 'Fecha pedindo DM']}[params.formato] || [];
  $('#sugestoes').innerHTML = sug.map(s => `<button type="button" class="btn">${escapar(s)}</button>`).join('');
  $('#sugestoes').querySelectorAll('button').forEach(b => b.onclick = () => { $('#pedido').value = b.textContent; enviar(); });
}
function bolha(quem, texto) {
  const el = document.createElement('div'); el.className = 'msg ' + (quem === 'eu' ? 'eu' : 'ia'); el.textContent = texto;
  $('#mensagens').appendChild(el); $('#mensagens').scrollTop = $('#mensagens').scrollHeight;
  return el;
}
function mensagensRefinar(mensagem) {
  const ctx = {...contexto(), parametros: params, roteiro_atual: roteiro};
  const msgs = [{role: 'user', content: 'Contexto e roteiro atual:\n' + JSON.stringify(ctx, null, 2)},
                {role: 'assistant', content: 'Entendido. O que você quer mudar?'}];
  for (const turno of conversa.slice(-12)) {
    const papel = turno.papel === 'usuario' ? 'user' : 'assistant';
    const texto = String(turno.texto || '').trim();
    if (texto && msgs[msgs.length - 1].role !== papel) msgs.push({role: papel, content: texto});
  }
  if (msgs[msgs.length - 1].role === 'user') msgs.push({role: 'assistant', content: 'Certo.'});
  msgs.push({role: 'user', content: mensagem});
  return msgs;
}
async function enviar() {
  const msg = $('#pedido').value.trim(); if (!msg) return;
  $('#pedido').value = ''; $('#erro3').hidden = true; bolha('eu', msg);
  $('#enviar').disabled = true;
  const pensando = bolha('ia', ''); pensando.innerHTML = '<span class="girando"></span>reescrevendo…';
  try {
    const texto = await Radar.chamarIA({modelo: CFG.modelo, maxTokens: CFG.max_tokens, thinking: {type: 'adaptive'},
      system: CFG.prompts.refinar, messages: mensagensRefinar(msg)});
    const dados = Radar.extrairJson(texto);
    pensando.remove();
    const resposta = String(dados.resposta || '').trim() || 'Feito.';
    conversa.push({papel: 'usuario', texto: msg}, {papel: 'ia', texto: resposta});
    roteiro = Radar.limparRoteiro(dados.roteiro || roteiro);
    renderRoteiro(); bolha('ia', resposta); $('#salvo').hidden = true;
  } catch (e) { pensando.remove(); mostrarErro('#erro3', e); }
  $('#enviar').disabled = false;
}
$('#enviar').onclick = enviar;
$('#pedido').onkeydown = e => { if (e.key === 'Enter') enviar(); };
$('#salvar').onclick = async () => {
  $('#salvar').disabled = true;
  const r = await Radar.salvarMinhaIdeia(CFG.nicho, {id: idSalvo, ideia: params.ideia, formato: params.formato,
    estilo: params.estilo, tom: params.tom, tamanho: params.tamanho, roteiro});
  idSalvo = r.id;
  $('#salvo').className = 'mensagem ' + (r.ok ? 'ok' : 'alerta');
  $('#salvo').innerHTML = (r.ok ? '✅ Salvo. ' : '⚠️ ' + escapar(r.recado || '') + ' A ideia ficou guardada aqui. ')
    + '<a href="index.html">Ver na agenda</a> · <a href="estudio.html">Criar outra</a>';
  $('#salvo').hidden = false;
  $('#salvar').disabled = false;
};
$('#copiar').onclick = () => Radar.copiar(Radar.textoRoteiro(roteiro), 'Roteiro copiado 📋');
$('#voltar1').onclick = () => etapa(1);
$('#voltar2').onclick = () => (opcoes.length ? etapa(2) : etapa(1));
function reabrir(id) {
  const item = Radar.minhasIdeias(CFG.nicho, CFG.galeria_publicada).find(i => i.id === id);
  if (!item) return;
  $('#ideia').value = item.ideia || ''; $('#formato').value = item.formato || 'video'; atualizarTamanhos();
  $('#tamanho').value = item.tamanho || ''; $('#estilo').value = item.estilo || ''; $('#tom').value = item.tom || '';
  lerParams(); roteiro = Radar.limparRoteiro(item.roteiro || {}); opcoes = []; conversa = [];
  idSalvo = id;
  $('#mensagens').innerHTML = '';
  bolha('ia', 'Reabri a ideia. O que você quer mudar?');
  renderRoteiro(); etapa(3);
}
async function iniciar() {
  montarMenus();
  conferirIA();
  window.addEventListener('focus', () => conferirIA(true));
  // abre a ligação com o banco antes de qualquer gravação, senão a ideia
  // criada aqui ficaria só neste navegador
  await Radar.abrirEstado(CFG.nicho);
  const idInicial = new URLSearchParams(location.search).get('id');
  if (idInicial) reabrir(idInicial);
}
iniciar();
"""


def pagina_estudio(config: dict, raiz: Path, nicho: str) -> str:
    dados = {
        "nicho": nicho, "nome": config["nome"],
        "menus": {"formatos": estudio_mod.FORMATOS, "estilos": estudio_mod.ESTILOS,
                  "tons": estudio_mod.TONS, "tamanhos": estudio_mod.TAMANHOS},
        "modelo": MODELO_ESCRITA, "max_tokens": MAX_TOKENS_ESTUDIO,
        "prompts": {"opcoes": estudio_mod._sistema(estudio_mod.PROMPT_OPCOES),
                    "refinar": estudio_mod._sistema(estudio_mod.PROMPT_REFINAR)},
        "contexto": _contexto_estudio(config, raiz, nicho),
        "galeria_publicada": galeria_publicada(raiz, nicho),
    }
    return documento(titulo=f"Estúdio — {config['nome']}", ativa="estudio",
                     corpo=CORPO_ESTUDIO, estilo_extra=ESTILO_ESTUDIO,
                     script=SCRIPT_ESTUDIO, dados=dados)


# ── Manual do nicho ──────────────────────────────────────────────────────

ESTILO_MANUAL = """
  section.manual { padding: 0 0 60px; }
  .manual-corpo { max-width: 720px; margin: 0 auto; }
  .manual-corpo h1 { font-size: 1.5rem; margin-bottom: 6px; }
  .manual-corpo h1 + p { color: var(--suave); margin-top: 0; }
  .manual-corpo h2 { font-size: .78rem; font-weight: 700; letter-spacing: .11em; text-transform: uppercase;
                     color: var(--suave); margin: 34px 0 10px; padding-top: 18px; border-top: 1px solid var(--borda-leve); }
  .manual-corpo h3 { font-size: 1rem; margin: 18px 0 6px; }
  .manual-corpo ul { padding-left: 20px; } .manual-corpo li { margin: 6px 0; } .manual-corpo p { margin: 8px 0; }
  .manual-corpo hr { border: 0; border-top: 1px solid var(--borda-leve); margin: 28px 0; }
"""


def pagina_manual(config: dict, raiz: Path, nicho: str) -> str:
    texto = manual_mod.carregar(raiz, nicho)
    if texto:
        corpo_manual = manual_mod.para_html(texto)
        intro = ("O que o radar aprendeu até agora com os virais do nicho: estruturas que "
                 "viralizam, vozes, aberturas com exemplos, vocabulário. É consolidado a cada "
                 "geração de agenda e lido pelo roteirista antes de escrever — no estúdio também.")
    else:
        corpo_manual = ('<div class="vazio-suave"><b>O manual ainda não existe.</b><br>'
                        'Ele é escrito ao fim de cada geração de agenda, a partir do que a '
                        'pesquisa da semana descobriu, e vem para o site na publicação seguinte.</div>')
        intro = "O caderno de aprendizado do nicho, destilado em regras acionáveis para quem escreve."
    corpo = f"""
<header class="hero container">
  <div class="selo">Manual do nicho</div>
  <h1>O que faz viralizar em <span>{escape(config['nome'])}</span></h1>
  <p class="sub">{escape(intro)}</p>
</header>
<section class="manual container"><div class="manual-corpo">{corpo_manual}</div></section>
"""
    return documento(titulo=f"Manual do nicho — {config['nome']}", ativa="manual",
                     corpo=corpo, estilo_extra=ESTILO_MANUAL)


# ── Ferramentas ──────────────────────────────────────────────────────────

ESTILO_FERRAMENTAS = """
  section.ferramentas { padding: 0 0 60px; }
  .chips-lista { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
  .chips-lista .chip { font-size: .78rem; padding: 5px 12px; }
  .pref-grade { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 12px; }
  .pref-bloco { background: var(--superficie); border-radius: var(--r-md); padding: 12px 14px; font-size: .86rem; }
  .pref-bloco b { display: block; font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; color: var(--suave); margin-bottom: 6px; }
  .pref-bloco ul { padding-left: 16px; margin: 0; }
  .lista-local { list-style: none; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; }
  .lista-local li { background: var(--superficie); border: 1px solid var(--borda-leve); border-radius: var(--r-md);
                    padding: 12px 14px; font-size: .86rem; }
  .lista-local li b { display: block; }
  .lista-local li span { color: var(--suave); }
  .nota { color: var(--suave); font-size: .8rem; margin-top: 8px; }
  code { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: .84em; background: var(--superficie);
         padding: 1px 6px; border-radius: 6px; }
"""

SO_NO_COMPUTADOR = [
    ("🎬", "Gerar a agenda pelo seu IP", "A coleta gratuita do TikTok roda pelo navegador do seu computador, "
     "que é o que o TikTok trata como uso normal. Na nuvem ela é bloqueada — por isso o botão fica no painel."),
    ("🔑", "Conectar TikTok", "O login fica guardado no navegador da coleta, na sua máquina. Sem ele as buscas voltam vazias."),
    ("🧪", "Testar coleta", "Só faz a busca de vídeos, sem IA e sem custo — mas precisa do navegador da coleta."),
    ("🎯", "Otimizar termos de busca", "Reescreve o arquivo do nicho no projeto; o site publicado não tem como gravar lá."),
    ("☁️", "Publicar no site", "Envia a agenda do painel para o GitHub; a Vercel publica em cerca de um minuto."),
    ("🔄", "Atualizar programa", "Baixa a versão nova do código para a pasta do projeto."),
]


def _dados_termos(config: dict, raiz: Path, nicho: str) -> dict:
    rodadas = termos_mod.carregar(raiz, nicho)
    resumo = termos_mod.desempenho(rodadas)
    palavras = list(config.get("buscas_por_palavra", []))
    hashtags = [str(h).lstrip("#") for h in config.get("hashtags_monitoradas", [])]
    perfis = [str(p) for p in config.get("perfis_referencia", []) or []]
    linhas = []
    for termo in palavras:
        d = resumo.get(f'"{termo}"', {})
        linhas.append({"termo": termo, "tipo": "palavra", **{k: d.get(k, 0) for k in ("rodadas", "coletados", "virais")}})
    for h in hashtags:
        d = resumo.get(f"#{h}", {})
        linhas.append({"termo": "#" + h, "tipo": "hashtag", **{k: d.get(k, 0) for k in ("rodadas", "coletados", "virais")}})
    return {"rodadas": len(rodadas), "ultima": rodadas[-1].get("data", "") if rodadas else "",
            "linhas": linhas, "perfis": perfis,
            "sugeridos": termos_mod.sugestoes_recorrentes(rodadas)}


def pagina_ferramentas(config: dict, raiz: Path, nicho: str) -> str:
    url_repo = _url_repositorio(raiz)
    dados = {
        "nicho": nicho, "nome": config["nome"],
        "url_repositorio": url_repo,
        "url_acao": f"{url_repo}/actions/workflows/agenda-semanal.yml" if url_repo else "",
        "modelo_escrita": MODELO_ESCRITA, "modelo_pesquisa": MODELO_PESQUISA,
        "termos": _dados_termos(config, raiz, nicho),
        "publicado_em": date.today().isoformat(),
    }
    itens_local = "".join(f"<li><b>{i} {escape(t)}</b><span>{escape(d)}</span></li>"
                          for i, t, d in SO_NO_COMPUTADOR)
    acao = (f'<a class="btn primario" href="{escape(dados["url_acao"], quote=True)}" target="_blank" '
            'rel="noopener">Abrir no GitHub Actions ↗</a>' if url_repo else
            '<span class="nota">O endereço do repositório não foi encontrado na publicação.</span>')
    corpo = f"""
<header class="hero container">
  <div class="selo">Ferramentas</div>
  <h1>O que dá para fazer <span>daqui mesmo</span></h1>
  <p class="sub">Tudo nesta página roda no seu navegador, sem depender do computador onde o painel
  está instalado. O que precisa da sua máquina está listado no fim, com o motivo.</p>
</header>
<section class="ferramentas container">

  <div class="cartao-ferramenta" id="chave">
    <h2><span class="icone">🤖</span> Estado da IA</h2>
    <p>O estúdio escreve com a chave da Anthropic guardada no servidor do site — a mesma para
       todo mundo que abre aqui. Ninguém precisa ter chave, e a chave não passa pelo navegador
       de ninguém.</p>
    <div class="mensagem" id="ia-estado">carregando…</div>
    <div class="acoes"><button class="btn" id="ia-testar">Testar a IA</button></div>

    <div id="ia-senha" hidden>
      <p class="nota" style="margin-top:16px"><b>Este site pede uma senha de acesso à IA.</b>
         Guarde a sua aqui — ela fica só neste aparelho.</p>
      <div class="linha-campos" style="margin-top:8px">
        <input type="password" id="senha-valor" placeholder="senha do site" autocomplete="off" aria-label="Senha de acesso à IA">
        <button class="btn primario" id="senha-salvar">Guardar</button>
        <button class="btn" id="senha-apagar">Esquecer</button>
      </div>
    </div>

    <details id="ia-propria" style="margin-top:16px">
      <summary style="cursor:pointer;font-size:.85rem;font-weight:700;color:var(--suave)">
        Usar uma chave própria (só se o site estiver sem chave)</summary>
      <p class="nota" style="margin-top:10px">Serve para quem abriu esta página fora do site
         publicado. A chave fica guardada só neste navegador e é usada direto com a Anthropic.</p>
      <div class="linha-campos" style="margin-top:8px">
        <input type="password" id="chave-valor" placeholder="sk-ant-..." autocomplete="off" aria-label="Chave própria da Anthropic">
        <button class="btn primario" id="chave-salvar">Guardar</button>
        <button class="btn" id="chave-apagar">Esquecer</button>
      </div>
    </details>

    <div class="mensagem" id="chave-recado" hidden></div>
    <p class="nota">Modelo do estúdio: <code>{escape(MODELO_ESCRITA)}</code>. Cada roteiro custa alguns centavos de dólar,
       na conta de quem configurou a chave do site.</p>
  </div>

  <div class="cartao-ferramenta" id="preferencias">
    <h2><span class="icone">🧭</span> Suas preferências reveladas</h2>
    <p>O que você põe na lista, marca como feita ou descarta na agenda vira um sinal de gosto —
       o estúdio lê isso antes de escrever. Calculado a partir das escolhas guardadas neste navegador.</p>
    <div id="pref-corpo"></div>
    <div class="acoes">
      <button class="btn" id="pref-exportar">⬇️ Exportar para o painel (JSON)</button>
    </div>
    <p class="nota">No painel, o arquivo vai em <code>dados/feedback-{escape(nicho)}.json</code>; a agenda semanal passa a usá-lo também.</p>
  </div>

  <div class="cartao-ferramenta" id="backup">
    <h2><span class="icone">💾</span> Backup das suas escolhas</h2>
    <p>Lista, feitas, descartadas, ganchos escolhidos e as ideias que você criou, num arquivo só.
       Serve para trocar de aparelho ou de navegador sem perder nada. A chave da IA não entra.</p>
    <div class="acoes">
      <button class="btn primario" id="backup-exportar">⬇️ Baixar backup</button>
      <button class="btn" id="backup-importar">⬆️ Restaurar de um arquivo</button>
      <input type="file" id="backup-arquivo" accept="application/json,.json" hidden>
    </div>
    <div class="mensagem" id="backup-recado" hidden></div>
  </div>

  <div class="cartao-ferramenta" id="nuvem">
    <h2><span class="icone">☁️</span> Gerar a agenda na nuvem</h2>
    <p>A agenda roda sozinha toda segunda-feira no GitHub Actions. Para gerar agora sem ligar o
       computador, abra o fluxo e clique em <b>Run workflow</b> — é preciso estar logado no GitHub com
       acesso ao repositório. Na nuvem a coleta usa o Apify como reserva (o TikTok bloqueia servidores),
       então o volume pode ser menor que o da coleta local.</p>
    <div class="acoes">{acao}</div>
  </div>

  <div class="cartao-ferramenta" id="termos">
    <h2><span class="icone">🎯</span> Termos de busca e o que renderam</h2>
    <p>As hashtags, palavras e perfis que a coleta monitora, com o desempenho acumulado de cada um.
       Trocar os termos continua sendo feito no painel (Otimizar) ou no arquivo do nicho.</p>
    <div id="termos-corpo"></div>
  </div>

  <div class="titulo-secao">Só no computador (pelo painel)</div>
  <ul class="lista-local">{itens_local}</ul>
  <p class="nota">Para abrir o painel: duplo clique em <code>abrir-painel</code> na pasta do projeto.</p>
</section>
"""
    return documento(titulo=f"Ferramentas — {config['nome']}", ativa="ferramentas",
                     corpo=corpo, estilo_extra=ESTILO_FERRAMENTAS,
                     script=SCRIPT_FERRAMENTAS, dados=dados)


SCRIPT_FERRAMENTAS = r"""
const CFG = JSON.parse(document.getElementById('dados-pagina').textContent);
const $ = s => document.querySelector(s);
const escapar = Radar.escapar;
function recado(sel, tipo, texto) { const r = $(sel); r.className = 'mensagem ' + tipo; r.innerHTML = texto; r.hidden = false; }

// ── estado da IA ─────────────────────────────────────────────────────
async function pintarIA(recarregar) {
  const estado = await Radar.estadoIA(recarregar);
  const el = $('#ia-estado');
  if (estado.configurada) {
    el.className = 'mensagem ok';
    el.innerHTML = '✅ <b>A IA está pronta.</b> A chave fica no servidor do site — o estúdio funciona para quem abrir esta página, sem configurar nada.';
  } else if (estado.servidor) {
    el.className = 'mensagem alerta';
    el.innerHTML = '⚠️ <b>O site ainda não tem chave da Anthropic.</b> Quem administra precisa criar a variável de ambiente <code>ANTHROPIC_API_KEY</code> na Vercel (Settings → Environment Variables) e publicar de novo.';
  } else {
    el.className = 'mensagem alerta';
    el.innerHTML = '⚠️ <b>Esta página não está ligada ao servidor da IA.</b> Isso acontece ao abrir o arquivo direto do computador. Pelo site publicado ou pelo painel, a IA funciona sozinha.';
  }
  $('#ia-senha').hidden = !estado.senha;
  $('#ia-propria').open = !estado.configurada;
  $('#ia-testar').disabled = !estado.configurada && !Radar.chave();
  pintarChavePropria();
  pintarSenha();
}
function pintarChavePropria() {
  const tem = !!Radar.chave();
  $('#chave-valor').placeholder = tem ? 'chave guardada neste navegador (sk-ant-…)' : 'sk-ant-...';
  $('#chave-apagar').hidden = !tem;
}
function pintarSenha() {
  const tem = !!Radar.senha();
  $('#senha-valor').placeholder = tem ? 'senha guardada neste aparelho' : 'senha do site';
  $('#senha-apagar').hidden = !tem;
}
$('#chave-salvar').onclick = () => {
  const r = Radar.salvarChave($('#chave-valor').value);
  recado('#chave-recado', r.ok ? 'ok' : 'erro', (r.ok ? '✅ ' : '⚠️ ') + escapar(r.recado));
  if (r.ok) { $('#chave-valor').value = ''; pintarIA(); }
};
$('#chave-valor').onkeydown = e => { if (e.key === 'Enter') $('#chave-salvar').click(); };
$('#chave-apagar').onclick = () => { Radar.apagarChave(); pintarIA(); recado('#chave-recado', 'ok', 'Chave própria esquecida.'); };
$('#senha-salvar').onclick = () => {
  Radar.salvarSenha($('#senha-valor').value);
  $('#senha-valor').value = ''; pintarSenha();
  recado('#chave-recado', 'ok', '✅ Senha guardada neste aparelho.');
};
$('#senha-valor').onkeydown = e => { if (e.key === 'Enter') $('#senha-salvar').click(); };
$('#senha-apagar').onclick = () => { Radar.apagarSenha(); pintarSenha(); recado('#chave-recado', 'ok', 'Senha esquecida.'); };
$('#ia-testar').onclick = async () => {
  $('#ia-testar').disabled = true;
  recado('#chave-recado', 'alerta', '<span class="girando"></span>Testando com uma chamada mínima…');
  try {
    await Radar.chamarIA({modelo: CFG.modelo_pesquisa, maxTokens: 8, system: 'Responda com uma palavra.',
                          messages: [{role: 'user', content: 'ok?'}]});
    recado('#chave-recado', 'ok', '✅ A IA respondeu. O estúdio está liberado.');
  } catch (e) { recado('#chave-recado', 'erro', '⚠️ ' + escapar(e.message)); }
  $('#ia-testar').disabled = false;
};

// ── preferências ─────────────────────────────────────────────────────
function lista(obj) {
  const itens = Object.entries(obj || {});
  return itens.length ? '<ul>' + itens.map(([k, v]) => `<li>${escapar(k || '(sem pilar)')} <span style="color:var(--suave)">×${v}</span></li>`).join('') + '</ul>'
                      : '<span style="color:var(--suave)">nada ainda</span>';
}
function pintarPreferencias() {
  const p = Radar.preferencias(CFG.nicho);
  if (!p) {
    $('#pref-corpo').innerHTML = '<div class="vazio-suave" style="margin-top:12px">Nenhuma escolha registrada ainda. Use a agenda: adicione à lista, marque como feita ou descarte — cada clique conta.</div>';
    $('#pref-exportar').disabled = true; return;
  }
  $('#pref-exportar').disabled = false;
  $('#pref-corpo').innerHTML = `<p class="nota" style="margin-top:10px">${p.ideias_avaliadas} ideia(s) avaliada(s) neste navegador.</p>
    <div class="pref-grade">
      <div class="pref-bloco"><b>Pilares que você escolhe</b>${lista(p.pilares_que_ela_escolhe)}</div>
      <div class="pref-bloco"><b>Pilares que você descarta</b>${lista(p.pilares_que_ela_descarta)}</div>
      <div class="pref-bloco"><b>Vozes que você escolhe</b>${lista(p.vozes_que_ela_escolhe)}</div>
      <div class="pref-bloco"><b>Vozes que você descarta</b>${lista(p.vozes_que_ela_descarta)}</div>
    </div>
    ${p.assuntos_descartados.length ? `<div class="pref-bloco" style="margin-top:12px"><b>Assuntos descartados (não voltam)</b><ul>${p.assuntos_descartados.map(t => `<li>${escapar(t)}</li>`).join('')}</ul></div>` : ''}`;
}
$('#pref-exportar').onclick = () => Radar.baixar(`feedback-${CFG.nicho}.json`, JSON.stringify(Radar.feedback(CFG.nicho), null, 2));

// ── backup ───────────────────────────────────────────────────────────
$('#backup-exportar').onclick = () => {
  const dados = Radar.exportarTudo();
  const n = Object.keys(dados.chaves).length;
  if (!n) { recado('#backup-recado', 'alerta', 'Ainda não há nada guardado neste navegador.'); return; }
  Radar.baixar(`radar-backup-${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(dados, null, 2));
  recado('#backup-recado', 'ok', `✅ Backup com ${n} registro(s) baixado.`);
};
$('#backup-importar').onclick = () => $('#backup-arquivo').click();
$('#backup-arquivo').onchange = async e => {
  const arquivo = e.target.files[0]; if (!arquivo) return;
  try {
    const n = Radar.importarTudo(await Radar.lerArquivo(arquivo));
    recado('#backup-recado', 'ok', `✅ ${n} registro(s) restaurado(s). Abra a agenda para ver.`);
    pintarPreferencias();
  } catch (err) { recado('#backup-recado', 'erro', '⚠️ ' + escapar(err.message)); }
  e.target.value = '';
};

// ── termos ───────────────────────────────────────────────────────────
function pintarTermos() {
  const t = CFG.termos;
  const chips = (rot, itens, prefixo) => itens.length ? `<div class="nota" style="margin-top:12px"><b>${rot}</b></div>
    <div class="chips-lista">${itens.map(i => `<span class="chip">${escapar((prefixo || '') + i)}</span>`).join('')}</div>` : '';
  let html = '';
  if (t.rodadas) {
    const linhas = [...t.linhas].sort((a, b) => b.virais - a.virais || b.coletados - a.coletados);
    html += `<p class="nota" style="margin-top:10px">${t.rodadas} coleta(s) na memória · última em ${escapar(t.ultima)}</p>
      <div class="rolagem"><table class="tabela"><thead><tr><th>Termo</th><th>Tipo</th><th class="num">Coletas</th><th class="num">Vídeos</th><th class="num">Virais</th></tr></thead><tbody>
      ${linhas.map(l => `<tr><td>${escapar(l.termo)}</td><td>${l.tipo}</td><td class="num">${l.rodadas}</td><td class="num">${l.coletados}</td><td class="num"><b>${l.virais}</b></td></tr>`).join('')}
      </tbody></table></div>`;
    html += chips('Sugeridos pela coleta (apareceram em mais de uma semana)', t.sugeridos);
  } else {
    html += `<div class="vazio-suave" style="margin-top:12px">Ainda não há histórico de coletas publicado — ele aparece aqui depois da primeira coleta local.</div>`;
    html += chips('Palavras-chave monitoradas', t.linhas.filter(l => l.tipo === 'palavra').map(l => l.termo));
    html += chips('Hashtags monitoradas', t.linhas.filter(l => l.tipo === 'hashtag').map(l => l.termo));
  }
  html += chips('Perfis de referência', t.perfis, '@');
  $('#termos-corpo').innerHTML = html;
}

pintarIA(); pintarPreferencias(); pintarTermos();

"""


def publicar_paginas(config: dict, raiz: Path, nicho: str) -> list[Path]:
    """Escreve estudio.html, manual.html e ferramentas.html em web/."""
    web = raiz / "web"
    web.mkdir(parents=True, exist_ok=True)
    saidas = {
        "estudio.html": pagina_estudio(config, raiz, nicho),
        "manual.html": pagina_manual(config, raiz, nicho),
        "ferramentas.html": pagina_ferramentas(config, raiz, nicho),
    }
    escritos = []
    for nome, html in saidas.items():
        destino = web / nome
        destino.write_text(html, encoding="utf-8")
        escritos.append(destino)
    return escritos
