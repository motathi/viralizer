"""Painel local: gere a agenda da semana com um clique, na sua máquina.

Sobe um servidor em http://127.0.0.1:8777 (só acessível neste computador) e
abre o navegador com um painel de botões:

- ▶ Gerar agenda desta semana — roda o pipeline completo aqui, pelo seu IP
- 🧪 Testar coleta — só busca os virais, sem gastar nada de IA
- 👀 Abrir agenda — abre o resultado no navegador
- ☁️ Publicar no site — envia para o GitHub (a Vercel publica sozinha)
- 🔄 Atualizar agora — aparece sozinho quando há versão nova do programa

Também atende /api/ia, a mesma rota que o site publicado usa para falar com a
Anthropic — aqui com a chave do .env. É o que faz o estúdio e as ferramentas do
site funcionarem igual abertos daqui ou da internet (ver api/ia.js).

Uso: dê um duplo clique em abrir-painel.bat (Windows), abrir-painel.command
(Mac) ou abrir-painel.sh (Linux). Ou rode: python -m src.painel.servidor
"""

import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dotenv import load_dotenv

from src import feedback as feedback_mod
from src.painel import estudio
from src.roteiros import manual as manual_mod
from src.roteiros.gerador import MODELO_ESCRITA, MODELO_PESQUISA

RAIZ = Path(__file__).resolve().parent.parent.parent
PORTA = 8777

# Estado compartilhado entre as requisições
estado = {"rodando": False, "acao": "", "log": [], "fim": None, "erro": False}
trava = threading.Lock()


# Erros técnicos comuns traduzidos para quem não é da área
DICAS = [
    ("No module named", "📦 Faltam programas de apoio. Feche esta janela e abra o "
                        "painel pelo atalho (abrir-painel) — ele instala tudo sozinho."),
    ("credit balance is too low", "💳 Os créditos da Anthropic acabaram. Recarregue em "
                                  "console.anthropic.com (Plans & Billing) e tente de novo."),
    ("Payment Required", "💳 Os créditos do Apify acabaram — eles renovam todo mês. "
                         "Enquanto isso, a coleta usa as outras fontes disponíveis."),
    ("ANTHROPIC_API_KEY", "🔑 A chave da Anthropic não foi encontrada. Confira o arquivo "
                          ".env na pasta do projeto."),
    ("Nenhuma pauta com âncora viral", "🔍 A coleta não encontrou virais suficientes hoje. "
                                       "Tente de novo mais tarde — nada foi cobrado."),
    ("navegador da coleta ainda não foi instalado", "🌐 Falta instalar o navegador que faz a "
     "coleta. Feche esta janela e abra o painel pelo atalho (abrir-painel) — ele instala sozinho."),
    ("não há histórico suficiente", "📊 Ainda faltam coletas para comparar. Gere a "
     "agenda mais uma ou duas vezes e o otimizador terá dados para decidir."),
    ("O TikTok pediu verificação", "🤖 O TikTok quer confirmar que você não é um robô. "
     "Resolva na janela do navegador que abriu — é uma vez só, depois fica salvo."),
    ("todas vieram sem vídeo", "🔑 O navegador da coleta não tem uma sessão do TikTok — "
     "por isso as buscas voltam vazias. Clique em 🔑 Conectar TikTok, faça login uma "
     "vez, e teste de novo."),
    ("não devolveu nenhum vídeo", "🚫 O TikTok não mostrou nenhum vídeo desta vez. "
     "Clique em 🔑 Conectar TikTok para fazer login e tente de novo."),
    ("Failed to establish a new connection", "🌐 Sem conexão com a internet, ou o serviço "
                                             "está fora do ar. Tente de novo em alguns minutos."),
    ("Author identity unknown", "🪪 O Git não sabia quem você é. O painel já configurou isso "
     "neste projeto — clique em Publicar de novo."),
    ("could not read Username", "🔐 O Git não está autenticado nesta máquina — por isso não "
                                "deu para publicar. As alterações ficaram salvas aqui."),
]


def _dica_para(linha: str) -> str | None:
    for marca, dica in DICAS:
        if marca.lower() in linha.lower():
            return dica
    return None


def _registrar(linha: str) -> None:
    texto = linha.rstrip()
    dica = _dica_para(texto)
    with trava:
        estado["log"].append(texto)
        if dica and dica not in estado["log"]:
            estado["log"].append(f"\n👉 {dica}\n")
        del estado["log"][:-400]  # mantém as últimas 400 linhas


def _executar(comando: list[str], acao: str) -> None:
    """Roda um comando mostrando a saída ao vivo no painel."""
    with trava:
        estado.update(rodando=True, acao=acao, log=[], fim=None, erro=False)
    _registrar(f"$ {' '.join(comando[-4:])}\n")
    try:
        proc = subprocess.Popen(
            comando, cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, encoding="utf-8", errors="replace",
            env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
        )
        for linha in proc.stdout:
            _registrar(linha)
        codigo = proc.wait()
    except Exception as e:  # noqa: BLE001 - o painel precisa mostrar qualquer falha
        _registrar(f"❌ Falha ao executar: {e}")
        codigo = 1

    with trava:
        estado["rodando"] = False
        estado["erro"] = codigo != 0
        estado["fim"] = datetime.now().strftime("%H:%M")
    _registrar("✅ Concluído!" if codigo == 0 else f"❌ Terminou com erro (código {codigo})")


def _iniciar(comando: list[str], acao: str) -> bool:
    with trava:
        if estado["rodando"]:
            return False
    threading.Thread(target=_executar, args=(comando, acao), daemon=True).start()
    return True


PAGINA_MANUAL = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Manual do nicho</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  :root { --grad: linear-gradient(45deg,#405DE6,#833AB4 30%,#C13584 50%,#E1306C 70%,#F77737);
          --tinta:#1c1b1f; --suave:#6f6b76; --borda:#eceaef }
  * { box-sizing:border-box } body { margin:0; font-family:Inter,"Segoe UI",system-ui,sans-serif;
  color:var(--tinta); background:#fff; line-height:1.6; padding:36px 18px 60px }
  main { max-width:680px; margin:0 auto }
  h1 { font-size:1.6rem; font-weight:800; letter-spacing:-.025em; margin:0 0 6px }
  h1 + p { color:var(--suave); margin-top:0 }
  h2 { font-size:.78rem; font-weight:700; letter-spacing:.11em; text-transform:uppercase;
       color:var(--suave); margin:34px 0 10px; padding-top:18px; border-top:1px solid var(--borda) }
  ul { padding-left:20px } li { margin:6px 0 } p { margin:8px 0 }
  hr { border:0; border-top:1px solid var(--borda); margin:28px 0 }
  .vazio { background:#fbfafc; border:1px solid var(--borda); border-radius:14px; padding:18px }
  a.voltar { display:inline-block; margin-bottom:22px; color:var(--suave); text-decoration:none; font-size:.9rem }
</style></head><body><main><a class="voltar" href="/">← painel</a>
{{CORPO}}
</main></body></html>"""


def _tem_chave() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def _salvar_chave(valor: str) -> tuple[bool, str]:
    """Grava a chave no .env, sem passar pelo Bloco de Notas.

    No Windows, salvar ".env" pelo Bloco de Notas produz ".env.txt" sem
    aviso, e o programa não acha a chave. Escrevendo daqui, o nome sai
    certo. As demais linhas do arquivo são preservadas.
    """
    valor = valor.strip().strip('"').strip("'")
    if not valor:
        return False, "Cole a chave antes de salvar."
    if not valor.startswith("sk-"):
        return False, "Isso não parece uma chave da Anthropic — ela começa com sk-ant-."
    if len(valor) < 20:
        return False, "A chave veio cortada. Copie de novo, inteira."

    env = RAIZ / ".env"
    linhas = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    for i, linha in enumerate(linhas):
        if linha.strip().startswith("ANTHROPIC_API_KEY"):
            linhas[i] = f"ANTHROPIC_API_KEY={valor}"
            break
    else:
        linhas.append(f"ANTHROPIC_API_KEY={valor}")
    env.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    os.environ["ANTHROPIC_API_KEY"] = valor  # vale já, sem reabrir o painel
    return True, "Chave salva."


def _versao() -> dict:
    """Diz se a cópia local é um clone do Git e se há versão nova publicada."""
    if not (RAIZ / ".git").exists():
        return {"git": False, "atras": 0,
                "aviso": "Esta pasta foi baixada como ZIP, então não recebe atualizações. "
                         "Para atualizar com um clique daqui em diante, baixe uma única vez "
                         "com o comando: git clone <endereço do repositório>"}
    # GIT_TERMINAL_PROMPT=0: sem isso, um repositório privado sem credencial
    # salva trava esperando uma senha que ninguém vai digitar aqui.
    ambiente = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        f = subprocess.run(["git", "fetch", "--quiet"], cwd=RAIZ, timeout=40,
                           capture_output=True, text=True, check=False, env=ambiente)
        if f.returncode != 0:
            return {"git": True, "atras": 0, "aviso": "",
                    "falha": _motivo_falha(f.stderr or "")}
        r = subprocess.run(["git", "rev-list", "--count", "HEAD..@{u}"], cwd=RAIZ,
                           capture_output=True, text=True, timeout=10, check=False)
        if r.returncode != 0:  # branch local sem par no servidor
            return {"git": True, "atras": 0, "aviso": "",
                    "falha": "Esta cópia está numa ramificação que não existe no servidor."}
        atras = int(r.stdout.strip() or 0)
    except Exception:  # noqa: BLE001 - sem rede, segue sem avisar
        return {"git": True, "atras": 0, "aviso": "", "falha": ""}
    return {"git": True, "atras": atras, "aviso": "", "falha": ""}


def _motivo_falha(erro: str) -> str:
    e = erro.lower()
    if "authentication" in e or "could not read" in e or "403" in e:
        return ("O Git não conseguiu entrar na sua conta do GitHub. "
                "O botão de atualizar ainda funciona — ele pede o login.")
    if "could not resolve host" in e or "unable to access" in e:
        return "Sem conexão com a internet para conferir se há versão nova."
    return ""


# a verificação de versão roda em segundo plano, para não travar a abertura
versao_cache = {"git": True, "atras": 0, "aviso": "", "falha": ""}


def _atualizar_versao_cache() -> None:
    """Reconfere de tempos em tempos: quem deixa o painel aberto por horas
    precisa ver a versão nova sem ter que fechar e abrir de novo."""
    while True:
        versao_cache.update(_versao())
        time.sleep(180)


def _nichos() -> list[str]:
    return sorted(p.stem for p in (RAIZ / "config" / "nichos").glob("*.yaml"))


def _info_agenda() -> dict:
    """Data da última geração e quantidade de ideias publicadas."""
    dados = sorted((RAIZ / "dados").glob("*.json")) if (RAIZ / "dados").exists() else []
    dados = [p for p in dados if not p.name.startswith("historico-")]
    if not dados:
        return {"quando": None, "ideias": 0}
    arquivo = max(dados, key=lambda p: p.stat().st_mtime)
    try:
        n = len(json.loads(arquivo.read_text(encoding="utf-8"))["roteiros"]["ideias"])
    except Exception:  # noqa: BLE001
        n = 0
    quando = datetime.fromtimestamp(arquivo.stat().st_mtime).strftime("%d/%m/%Y às %H:%M")
    return {"quando": quando, "ideias": n}


PAGINA = """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Painel — Radar de Conteúdo Viral</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root { --grad: linear-gradient(45deg,#405DE6,#833AB4 30%,#C13584 50%,#E1306C 70%,#F77737);
          --tinta:#1c1b1f; --suave:#6f6b76; --borda:#eceaef; --fundo:#fff;
          --painel:#fbfafc; --rosa:#C13584; }
  * { box-sizing:border-box; margin:0 }
  body { font-family:Inter,"Segoe UI",system-ui,sans-serif; background:var(--fundo);
         color:var(--tinta); line-height:1.55; padding:36px 18px 56px; }
  .wrap { max-width:720px; margin:0 auto; display:flex; flex-direction:column; gap:26px }
  h1 { font-size:1.55rem; font-weight:800; letter-spacing:-.025em }
  h1 span { background:var(--grad); -webkit-background-clip:text; background-clip:text;
            -webkit-text-fill-color:transparent }
  .sub { color:var(--suave); font-size:.9rem; margin-top:4px }
  h2 { font-size:.75rem; font-weight:700; letter-spacing:.11em; text-transform:uppercase;
       color:var(--suave); margin-bottom:10px }

  .banner { display:none; border-radius:14px; padding:13px 16px; font-size:.88rem }
  .banner.visivel { display:block }
  .banner.nova { background:#f4f0ff; border:1px solid #ded0ff; color:#4a2b8c }
  .banner.zip { background:#fff7e8; border:1px solid #ffe2ab; color:#7a5200 }
  .linha-chave { display:flex; gap:8px; margin-top:10px; flex-wrap:wrap }
  .linha-chave input { flex:1 1 260px; font:inherit; font-size:.88rem; padding:10px 14px;
                       border-radius:999px; border:1.5px solid #e8d9b4; background:#fff;
                       color:var(--tinta) }
  .erro-chave { display:block; margin-top:8px; font-weight:600 }

  .status { background:var(--painel); border:1px solid var(--borda); border-radius:14px;
            padding:15px 18px; font-size:.92rem }

  .lista { list-style:none; display:flex; flex-direction:column; gap:10px; padding:0 }
  .item { display:grid; grid-template-columns:auto 1fr auto; gap:16px; align-items:center;
          border:1px solid var(--borda); border-radius:16px; padding:16px 18px;
          background:var(--fundo) }
  .item .n, .item .icone { align-self:start; margin-top:1px }
  .item .n { width:26px; height:26px; border-radius:50%; background:var(--grad); color:#fff;
             font-size:.8rem; font-weight:700; display:grid; place-items:center }
  .item .icone { font-size:1.15rem; width:26px; text-align:center }
  .item b { font-size:.98rem; font-weight:700; display:block }
  .item p { color:var(--suave); font-size:.85rem; margin-top:2px }
  .item select { margin-top:9px }

  button, a.btn { font:inherit; font-size:.9rem; font-weight:700; padding:11px 20px;
                  border-radius:999px; border:1.5px solid var(--borda); background:var(--fundo);
                  color:var(--tinta); cursor:pointer; transition:border-color .18s,color .18s;
                  text-decoration:none; white-space:nowrap; text-align:center }
  button:hover:not(:disabled), a.btn:hover { border-color:var(--rosa); color:var(--rosa) }
  a.principal-link { background:var(--grad); border-color:transparent; color:#fff }
  a.principal-link:hover { color:#fff; filter:brightness(1.07) }
  button.principal { background:var(--grad); border-color:transparent; color:#fff;
                     box-shadow:0 8px 22px -10px rgba(131,58,180,.55) }
  button.principal:hover:not(:disabled) { filter:brightness(1.07); color:#fff }
  button:disabled { opacity:.45; cursor:not-allowed }
  button:focus-visible, a.btn:focus-visible, select:focus-visible {
    outline:2px solid var(--rosa); outline-offset:2px }
  select { font:inherit; font-size:.85rem; padding:9px 14px; border-radius:999px;
           border:1.5px solid var(--borda); background:var(--painel); color:var(--tinta);
           cursor:pointer }

  .log-caixa { position:relative }
  .log-caixa #copiarLog { position:absolute; top:10px; right:10px; font-size:.78rem; padding:6px 12px;
    background:#2a272e; border-color:#3d3944; color:#efe9f1 }
  .log-caixa #copiarLog:hover { border-color:var(--rosa); color:#fff }
  #log { background:#1b191e; color:#efe9f1; font-family:ui-monospace,Menlo,Consolas,monospace;
         font-size:.8rem; line-height:1.55; border-radius:14px; padding:16px 18px;
         white-space:pre-wrap; max-height:400px; overflow:auto; display:none }
  #log.visivel { display:block }
  .rodape { color:var(--suave); font-size:.82rem }
  .girando { display:inline-block; width:13px; height:13px; border:2px solid #e2dfe6;
             border-top-color:var(--rosa); border-radius:50%; animation:g .8s linear infinite;
             margin-right:8px; vertical-align:-1px }
  @keyframes g { to { transform:rotate(360deg) } }
  @media (prefers-reduced-motion:reduce) { .girando { animation:none } }
  @media (max-width:560px) {
    .item { grid-template-columns:auto 1fr; row-gap:12px }
    .item button, .item a.btn { grid-column:1 / -1 }
  }
</style></head><body><div class="wrap">
  <header>
    <h1>Radar de <span>Conteúdo Viral</span></h1>
    <p class="sub">Tudo roda neste computador. Nada sai daqui até você mandar publicar.</p>
  </header>

  <div class="banner" id="avisoChave"></div>
  <div class="banner" id="atualizacao"></div>
  <div class="status" id="status">carregando…</div>

  <section>
    <h2>Toda semana</h2>
    <ol class="lista">
      <li class="item">
        <span class="n">1</span>
        <div>
          <b>Gerar a agenda</b>
          <p>Busca os vídeos que viralizaram no nicho e escreve 10 ideias com roteiro
             pronto. Leva de 5 a 10 minutos e consome créditos da IA.</p>
          <select id="nicho" aria-label="Nicho"></select>
        </div>
        <button class="principal" id="gerar">Gerar agenda</button>
      </li>
      <li class="item">
        <span class="n">2</span>
        <div>
          <b>Conferir o resultado</b>
          <p>Abre a agenda aqui no computador, com os roteiros e os vídeos virais que
             serviram de base para cada ideia.</p>
        </div>
        <a class="btn" id="abrir" href="/agenda" target="_blank" rel="noopener">Abrir agenda</a>
      </li>
      <li class="item">
        <span class="n">3</span>
        <div>
          <b>Publicar no site</b>
          <p>Envia a agenda para o site na internet, para abrir do celular e compartilhar
             o link. Só depois disso ela sai deste computador.</p>
        </div>
        <button id="publicar">Publicar</button>
      </li>
    </ol>
  </section>

  <section>
    <h2>Criar a partir de uma ideia sua</h2>
    <ul class="lista">
      <li class="item">
        <span class="icone">✨</span>
        <div>
          <b>Estúdio</b>
          <p>Você dá a ideia e escolhe formato (stories, carrossel ou vídeo), estilo e
             tom. A IA escreve três opções em ângulos diferentes; você escolhe uma,
             ajusta conversando com ela, e salva — a ideia entra na agenda
             junto com as das outras semanas.</p>
        </div>
        <a class="btn principal-link" id="estudio" href="/estudio">Abrir estúdio</a>
      </li>
    </ul>
  </section>

  <section>
    <h2>Quando precisar</h2>
    <ul class="lista">
      <li class="item">
        <span class="icone">🔑</span>
        <div>
          <b>Conectar TikTok</b>
          <p>Login no TikTok, uma vez só. Sem sessão, o TikTok responde as buscas com
             lista vazia e a agenda não tem de onde sair.</p>
        </div>
        <button id="conectarTiktok">Conectar</button>
      </li>
      <li class="item">
        <span class="icone">🧪</span>
        <div>
          <b>Testar coleta</b>
          <p>Faz só a busca de vídeos e para por aí — não escreve roteiro, não usa a IA,
             não custa nada. Serve para conferir se o TikTok está respondendo.</p>
        </div>
        <button id="testar">Testar</button>
      </li>
      <li class="item">
        <span class="icone">📘</span>
        <div>
          <b>Manual do nicho</b>
          <p>O que o radar aprendeu até agora: estruturas que viralizam, vozes,
             aberturas com exemplos, vocabulário — consolidado semana a semana e
             lido pelo roteirista antes de escrever.</p>
        </div>
        <a class="btn" id="manual" href="/manual" target="_blank" rel="noopener">Ler</a>
      </li>
      <li class="item">
        <span class="icone">🎯</span>
        <div>
          <b>Otimizar termos de busca</b>
          <p>Olha o desempenho de cada termo nas últimas coletas, tira os que
             nunca trouxeram viral e propõe outros a partir do que os virais do
             nicho estão usando. Precisa de pelo menos 2 coletas no histórico.</p>
        </div>
        <button id="otimizarTermos">Otimizar</button>
      </li>
      <li class="item">
        <span class="icone">🔄</span>
        <div>
          <b>Atualizar programa</b>
          <p>Baixa a versão mais recente, com as correções e melhorias.</p>
        </div>
        <button id="atualizarPrograma">Atualizar</button>
      </li>
    </ul>
  </section>

  <div class="log-caixa" id="logCaixa" hidden>
    <button id="copiarLog" title="Copia tudo que está na tela preta">📋 Copiar tela preta</button>
    <div id="log"></div>
  </div>
  <p class="rodape">💡 Pode deixar esta aba aberta enquanto trabalha — o progresso
     aparece aqui. A janela preta precisa continuar aberta: é ela que faz o trabalho.</p>
</div>
<script>
const $ = s => document.querySelector(s);
const ACOES = { gerar:'/gerar', testar:'/testar', publicar:'/publicar',
                conectarTiktok:'/tiktok-login', atualizarPrograma:'/atualizar',
                otimizarTermos:'/otimizar' };
const COM_NICHO = ['gerar', 'testar', 'otimizarTermos'];
let semChave = false;

async function carregarNichos() {
  const r = await (await fetch('/nichos')).json();
  $('#nicho').innerHTML = r.nichos.map(n =>
    `<option value="${n}">${n.replace(/-/g,' ')}</option>`).join('');
}

function pintar(e) {
  for (const id of Object.keys(ACOES)) $('#' + id).disabled = e.rodando;
  if (semChave) {
    $('#gerar').disabled = true;
    $('#gerar').title = 'Cole a chave da Anthropic no aviso acima para liberar';
  } else {
    $('#gerar').removeAttribute('title');
  }
  const s = $('#status');
  if (e.rodando) {
    s.innerHTML = `<span class="girando"></span> <b>${e.acao}</b> — em andamento…`;
  } else if (e.agenda.quando) {
    const fim = e.fim ? ` · última ação às ${e.fim}${e.erro ? ' (com erro)' : ''}` : '';
    s.innerHTML = `📅 Agenda com <b>${e.agenda.ideias} ideias</b>, gerada em <b>${e.agenda.quando}</b>${fim}`;
  } else {
    s.innerHTML = 'Nenhuma agenda ainda — comece pelo passo 1.';
  }
  if (e.log.length) {
    const l = $('#log');
    const colado = l.scrollTop + l.clientHeight >= l.scrollHeight - 30;
    l.textContent = e.log.join('\\n');
    l.classList.add('visivel');
    $('#logCaixa').hidden = false;
    if (colado) l.scrollTop = l.scrollHeight;
  }
}

async function conferirChave() {
  let temChave;
  try { temChave = (await (await fetch('/chaves')).json()).anthropic; }
  catch (_) { return; }
  semChave = !temChave;
  const el = $('#avisoChave');
  if (temChave) { el.className = 'banner'; el.innerHTML = ''; el.dataset.pedindo = ''; return; }
  if (el.dataset.pedindo === 'sim') return;   // não apagar o que já está sendo digitado
  el.dataset.pedindo = 'sim';
  el.className = 'banner visivel zip';
  el.innerHTML = `<b>Falta a chave da Anthropic.</b> Sem ela o programa encontra os
    virais, mas não escreve os roteiros. Pegue em console.anthropic.com →
    Settings → API keys e cole aqui:
    <div class="linha-chave">
      <input type="password" id="chaveValor" placeholder="sk-ant-..." autocomplete="off"
             aria-label="Chave da Anthropic">
      <button id="salvarChave">Salvar chave</button>
    </div>
    <span class="erro-chave" id="chaveErro"></span>`;
  const salvar = async () => {
    const r = await fetch('/chave', {method:'POST', body: $('#chaveValor').value});
    const d = await r.json();
    if (d.ok) { el.dataset.pedindo = ''; conferirChave(); atualizar(); }
    else { $('#chaveErro').textContent = '⚠️ ' + d.recado; }
  };
  $('#salvarChave').onclick = salvar;
  $('#chaveValor').onkeydown = ev => { if (ev.key === 'Enter') salvar(); };
}

async function conferirVersao() {
  try {
    const v = await (await fetch('/versao')).json();
    const el = $('#atualizacao');
    if (!v.git && v.aviso) {
      el.className = 'banner visivel zip';
      el.innerHTML = `📦 ${v.aviso}`;
    } else if (v.atras > 0) {
      el.className = 'banner visivel nova';
      el.innerHTML = `✨ Tem versão nova do programa (${v.atras} melhoria${v.atras>1?'s':''}) — ` +
                     `use <b>Atualizar programa</b> aqui embaixo.`;
    } else if (v.falha) {
      el.className = 'banner visivel zip';
      el.innerHTML = `⚠️ ${v.falha}`;
    } else {
      el.className = 'banner';
    }
  } catch (_) {}
}

async function atualizar() {
  try { pintar(await (await fetch('/status')).json()); } catch (_) {}
}

for (const [id, rota] of Object.entries(ACOES)) {
  $('#' + id).onclick = async () => {
    const alvo = COM_NICHO.includes(id)
      ? rota + '?nicho=' + encodeURIComponent($('#nicho').value) : rota;
    await fetch(alvo, {method:'POST'});
    atualizar();
    if (id === 'atualizarPrograma') setTimeout(conferirVersao, 20000);
  };
}

$('#copiarLog').onclick = async () => {
  const b = $('#copiarLog');
  try { await navigator.clipboard.writeText($('#log').textContent); b.textContent = '✅ Copiado'; }
  catch (_) { b.textContent = '⚠️ Não deu — selecione o texto e use Ctrl+C'; }
  setTimeout(() => b.textContent = '📋 Copiar tela preta', 2500);
};
carregarNichos();
conferirChave();
conferirVersao();
setInterval(conferirVersao, 60000);
atualizar();
setInterval(atualizar, 1500);
</script></body></html>
"""


# ── estado compartilhado (mesma rota do site; ver api/estado.js) ────────

def _supabase() -> tuple[str, str]:
    return (os.environ.get("SUPABASE_URL", "").strip().rstrip("/"),
            os.environ.get("SUPABASE_SECRET_KEY", "").strip())


def _cabecalhos_supabase(chave: str) -> dict:
    """Chave nova (sb_secret_…) não é JWT: vai só em apikey. A antiga, nos dois."""
    cabecalhos = {"apikey": chave, "Content-Type": "application/json"}
    if chave.startswith("ey"):
        cabecalhos["Authorization"] = f"Bearer {chave}"
    return cabecalhos


def _chamar_supabase(caminho: str, metodo: str = "GET", corpo: dict | None = None):
    import requests
    url, chave = _supabase()
    r = requests.request(metodo, f"{url}/rest/v1/{caminho}",
                         headers=_cabecalhos_supabase(chave), json=corpo, timeout=20)
    r.raise_for_status()
    return r.json() if r.status_code != 204 and r.content else None


def _erro_banco(e: Exception) -> str:
    codigo = getattr(getattr(e, "response", None), "status_code", 0)
    if codigo in (401, 403):
        return ("O Supabase recusou a chave. Confira SUPABASE_SECRET_KEY no .env — "
                "tem de ser a chave secreta, não a publicável.")
    if codigo == 404:
        return "As tabelas do Radar não existem neste projeto. Rode supabase/schema.sql no SQL Editor."
    if codigo == 540:
        return "O projeto do Supabase está pausado. Clique em Resume no painel do Supabase."
    return f"Não consegui falar com o banco: {str(e).splitlines()[0][:200]}"


# ── proxy da IA (mesma rota do site publicado; ver api/ia.js) ────────────

MODELOS_IA = (MODELO_PESQUISA, MODELO_ESCRITA)
MAX_TOKENS_IA = 20000


def _erro_ia(e: Exception) -> str:
    """Erro técnico traduzido para quem vai ler na tela."""
    texto = str(e).lower()
    if "authentication" in texto or "x-api-key" in texto or "api_key" in texto:
        return ("A chave da Anthropic no arquivo .env não foi aceita. "
                "Confira em console.anthropic.com.")
    if "credit balance" in texto:
        return "Os créditos da Anthropic acabaram. Recarregue em console.anthropic.com."
    if "rate_limit" in texto or "429" in texto:
        return "A Anthropic pediu para esperar um pouco. Tente de novo em um minuto."
    if "overloaded" in texto or "529" in texto:
        return "A Anthropic está sobrecarregada agora. Tente de novo em instantes."
    return f"A IA respondeu com erro: {str(e).splitlines()[0][:200]}"


def _arquivo_do_site(caminho: str) -> Path | None:
    """Página de web/ correspondente ao caminho pedido, ou None."""
    from urllib.parse import unquote
    web = (RAIZ / "web").resolve()
    alvo = (web / unquote(caminho).lstrip("/")).resolve()
    if alvo.is_file() and alvo.suffix == ".html" and web in alvo.parents:
        return alvo
    return None


class Painel(BaseHTTPRequestHandler):
    def _responder(self, corpo: bytes, tipo: str = "text/html; charset=utf-8",
                   codigo: int = 200) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, dados: dict) -> None:
        self._responder(json.dumps(dados, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802 - assinatura da biblioteca padrão
        caminho, _, consulta = self.path.partition("?")
        if estudio.tratar(self, "GET", caminho, consulta, b""):
            return
        if caminho == "/":
            self._responder(PAGINA.encode("utf-8"))
        elif caminho == "/nichos":
            self._json({"nichos": _nichos()})
        elif caminho == "/versao":
            self._json(versao_cache)
        elif caminho == "/chaves":
            self._json({"anthropic": _tem_chave()})
        elif caminho == "/manual":
            nichos = _nichos()
            consulta = self.path.partition("?")[2]
            nicho = dict(x.split("=", 1) for x in consulta.split("&")
                         if "=" in x).get("nicho") or (nichos[0] if nichos else "")
            arquivo = RAIZ / "dados" / f"manual-{nicho}.md"
            if arquivo.exists():
                corpo = manual_mod.para_html(arquivo.read_text(encoding="utf-8"))
            else:
                corpo = ('<div class="vazio"><b>O manual ainda não existe.</b><br>'
                         'Ele é escrito ao fim de cada geração de agenda, a partir do que a '
                         'pesquisa da semana descobriu. Gere a primeira agenda e volte aqui.</div>')
            self._responder(PAGINA_MANUAL.replace("{{CORPO}}", corpo).encode("utf-8"))
        elif caminho == "/api/ia":
            self._json({"configurada": _tem_chave(), "senha": False, "painel": True,
                        "modelos": list(MODELOS_IA), "max_tokens": MAX_TOKENS_IA})
        elif caminho == "/api/estado":
            self._estado_get(consulta)
        elif caminho == "/status":
            with trava:
                self._json({**estado, "agenda": _info_agenda()})
        elif caminho == "/agenda":
            arquivo = RAIZ / "web" / "index.html"
            if arquivo.exists():
                self._responder(arquivo.read_bytes())
            else:
                self._responder(b"Nenhuma agenda gerada ainda.", codigo=404)
        elif (arquivo := _arquivo_do_site(caminho)) is not None:
            # as demais páginas do site (estúdio, manual, ferramentas), para a
            # navegação funcionar aqui também
            self._responder(arquivo.read_bytes())
        else:
            self._responder(b"nao encontrado", codigo=404)

    def do_POST(self) -> None:  # noqa: N802
        caminho, _, consulta = self.path.partition("?")
        if caminho.startswith(("/estudio", "/galeria")):
            tamanho = int(self.headers.get("Content-Length") or 0)
            if estudio.tratar(self, "POST", caminho, consulta, self.rfile.read(tamanho)):
                return
        if caminho == "/api/estado":
            tamanho = int(self.headers.get("Content-Length") or 0)
            self._estado_post(self.rfile.read(tamanho))
            return
        if caminho == "/api/ia":
            tamanho = int(self.headers.get("Content-Length") or 0)
            self._proxy_ia(self.rfile.read(tamanho))
            return
        if caminho == "/gerar":
            nicho = dict(p.split("=", 1) for p in consulta.split("&") if "=" in p).get("nicho", "")
            nicho = nicho.replace("%20", " ")
            if nicho not in _nichos():
                self._json({"ok": False, "erro": "nicho inválido"})
                return
            ok = _iniciar([sys.executable, "-m", "src.main", "--nicho", nicho,
                           "--publicar-site"], "Gerando a agenda")
            self._json({"ok": ok})
        elif caminho == "/testar":
            nicho = dict(x.split("=", 1) for x in consulta.split("&") if "=" in x).get("nicho", "")
            if nicho not in _nichos():
                self._json({"ok": False, "erro": "nicho inválido"})
                return
            ok = _iniciar([sys.executable, "-m", "src.main", "--nicho", nicho,
                           "--coleta", "local", "--apenas-descoberta"],
                          "Testando a coleta (sem custo)")
            self._json({"ok": ok})
        elif caminho == "/otimizar":
            nicho = dict(x.split("=", 1) for x in consulta.split("&")
                         if "=" in x).get("nicho", "")
            if nicho not in _nichos():
                self._json({"ok": False, "erro": "nicho inválido"})
                return
            ok = _iniciar([sys.executable, "-m", "src.painel.otimizar",
                           "--nicho", nicho], "Otimizando os termos de busca")
            self._json({"ok": ok})
        elif caminho == "/feedback":
            tamanho = int(self.headers.get("Content-Length") or 0)
            try:
                dados = json.loads(self.rfile.read(tamanho).decode("utf-8", "ignore"))
            except ValueError:
                self._json({"ok": False}); return
            nicho = str(dados.get("nicho", ""))
            if nicho not in _nichos():
                self._json({"ok": False, "erro": "nicho inválido"}); return
            total = feedback_mod.registrar(RAIZ, nicho, str(dados.get("semana", "")),
                                           dados.get("ideias") or [])
            self._json({"ok": True, "registradas": total})
        elif caminho == "/chave":
            tamanho = int(self.headers.get("Content-Length") or 0)
            corpo = self.rfile.read(tamanho).decode("utf-8", "ignore")
            ok, recado = _salvar_chave(corpo)
            self._json({"ok": ok, "recado": recado})
        elif caminho == "/tiktok-login":
            ok = _iniciar([sys.executable, "-m", "src.descoberta.tiktok_conta"],
                          "Conectando sua conta do TikTok")
            self._json({"ok": ok})
        elif caminho == "/atualizar":
            ok = _iniciar([sys.executable, "-m", "src.painel.atualizar"],
                          "Atualizando o programa")
            self._json({"ok": ok})
        elif caminho == "/publicar":
            ok = _iniciar([sys.executable, "-m", "src.painel.publicar"], "Publicando no site")
            self._json({"ok": ok})
        else:
            self._responder(b"nao encontrado", codigo=404)

    def _estado_get(self, consulta: str) -> None:
        """O estado e as ideias guardadas no banco, como o site espera."""
        from urllib.parse import parse_qs, quote
        nicho = (parse_qs(consulta).get("nicho") or ["padrao"])[0]
        url, chave = _supabase()
        if not (url and chave):
            self._json({"configurado": False, "estado": {}, "ideias": []})
            return
        try:
            linhas = _chamar_supabase(f"radar_estado?nicho=eq.{quote(nicho)}&select=*") or []
            ideias = _chamar_supabase(
                f"radar_ideias?nicho=eq.{quote(nicho)}&select=*&order=atualizado_em.desc") or []
        except Exception as e:  # noqa: BLE001 - a página mostra o recado
            self._json({"configurado": True, "erro": "banco", "recado": _erro_banco(e),
                        "estado": {}, "ideias": []})
            return
        estado = {l["ideia_id"]: {"lista": l["lista"], "feito": l["feita"],
                                  "descartada": l["descartada"], "gancho": l["gancho"],
                                  "formato": l["formato"]} for l in linhas}
        self._json({"configurado": True, "estado": estado,
                    "ideias": [{**i, "origem": "banco"} for i in ideias]})

    def _estado_post(self, corpo: bytes) -> None:
        url, chave = _supabase()
        if not (url and chave):
            self._json({"ok": False, "configurado": False})
            return
        try:
            pedido = json.loads(corpo.decode("utf-8", "ignore") or "{}")
        except ValueError:
            self._json({"ok": False, "recado": "Pedido inválido."}); return
        nicho = str(pedido.get("nicho") or "padrao")
        item = str(pedido.get("id") or "")
        if not item:
            self._json({"ok": False, "recado": "Pedido sem id."}); return
        rotas = {"estado": ("radar_definir_estado",
                            {"p_nicho": nicho, "p_ideia_id": item, "p_estado": pedido.get("dados") or {}}),
                 "ideia": ("radar_salvar_ideia",
                           {"p_nicho": nicho, "p_id": item, "p_dados": pedido.get("dados") or {}}),
                 "apagar": ("radar_apagar_ideia", {"p_nicho": nicho, "p_id": item})}
        if pedido.get("acao") not in rotas:
            self._json({"ok": False, "recado": "Ação desconhecida."}); return
        funcao, argumentos = rotas[pedido["acao"]]
        try:
            _chamar_supabase(f"rpc/{funcao}", "POST", argumentos)
        except Exception as e:  # noqa: BLE001
            self._json({"ok": False, "recado": _erro_banco(e)}); return
        self._json({"ok": True})

    def _proxy_ia(self, corpo: bytes) -> None:
        """Repassa um pedido do site para a Anthropic, com a chave do .env.

        Devolve os pedaços do texto no mesmo formato (SSE) que api/ia.js usa,
        para as páginas não precisarem saber onde estão rodando.
        """
        if not _tem_chave():
            self._json({"erro": "sem_chave", "recado": "Falta a chave da Anthropic no "
                        "arquivo .env. Cole a chave no aviso do topo do painel."})
            return
        try:
            pedido = json.loads(corpo.decode("utf-8", "ignore") or "{}")
        except ValueError:
            self._json({"erro": "pedido_invalido", "recado": "Pedido inválido."})
            return
        modelo = str(pedido.get("modelo", ""))
        if modelo not in MODELOS_IA:
            self._json({"erro": "modelo", "recado": "Modelo não permitido."})
            return
        mensagens = [{"role": "assistant" if m.get("role") == "assistant" else "user",
                      "content": str(m.get("content", ""))}
                     for m in (pedido.get("messages") or []) if isinstance(m, dict)]
        if not mensagens:
            self._json({"erro": "pedido_invalido", "recado": "Pedido sem mensagens."})
            return

        extras = {}
        if pedido.get("thinking") and modelo == MODELO_ESCRITA:
            extras["thinking"] = {"type": "adaptive"}

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        def enviar(evento: dict) -> None:
            self.wfile.write(f"data: {json.dumps(evento, ensure_ascii=False)}\n\n"
                             .encode("utf-8"))
            self.wfile.flush()

        try:
            import anthropic
            cliente = anthropic.Anthropic()
            with cliente.messages.stream(
                model=modelo, system=str(pedido.get("system", "")), messages=mensagens,
                max_tokens=min(int(pedido.get("max_tokens") or 16000), MAX_TOKENS_IA),
                **extras,
            ) as stream:
                for texto in stream.text_stream:
                    enviar({"type": "content_block_delta",
                            "delta": {"type": "text_delta", "text": texto}})
                parada = stream.get_final_message().stop_reason
            enviar({"type": "message_delta", "delta": {"stop_reason": parada}})
        except Exception as e:  # noqa: BLE001 - a página mostra o recado
            try:
                enviar({"type": "error", "error": {"message": _erro_ia(e)}})
            except OSError:
                pass

    def log_message(self, *_args) -> None:
        """Silencia o log de acessos do servidor (o painel já mostra o que importa)."""


def _conferir_dependencias() -> bool:
    faltando = []
    for modulo, pacote in (("yaml", "PyYAML"), ("dotenv", "python-dotenv"),
                           ("requests", "requests"), ("anthropic", "anthropic")):
        try:
            __import__(modulo)
        except ImportError:
            faltando.append(pacote)
    if faltando:
        print("\n  ⚠️  Faltam programas de apoio: " + ", ".join(faltando))
        print("  Instale com este comando e abra o painel de novo:\n")
        print(f"      {sys.executable} -m pip install -r requirements.txt\n")
    return not faltando


def main() -> None:
    load_dotenv(RAIZ / ".env")
    _conferir_dependencias()
    threading.Thread(target=_atualizar_versao_cache, daemon=True).start()
    servidor = ThreadingHTTPServer(("127.0.0.1", PORTA), Painel)
    url = f"http://127.0.0.1:{PORTA}"
    print(f"\n  🎬 Painel do Radar de Conteúdo Viral")
    print(f"  Abra no navegador: {url}")
    print("  Para encerrar, feche esta janela.\n")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n  Painel encerrado.")


if __name__ == "__main__":
    main()
