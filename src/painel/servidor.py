"""Painel local: gere a agenda da semana com um clique, na sua máquina.

Sobe um servidor em http://127.0.0.1:8777 (só acessível neste computador) e
abre o navegador com um painel de botões:

- ▶ Gerar agenda desta semana — roda o pipeline completo aqui, pelo seu IP
- 🧪 Testar coleta — só busca os virais, sem gastar nada de IA
- 👀 Abrir agenda — abre o resultado no navegador
- ☁️ Publicar no site — envia para o GitHub (a Vercel publica sozinha)
- 🔄 Atualizar agora — aparece sozinho quando há versão nova do programa

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
    ("O TikTok pediu verificação", "🤖 O TikTok quer confirmar que você não é um robô. "
     "Resolva na janela do navegador que abriu — é uma vez só, depois fica salvo."),
    ("todas vieram sem vídeo", "🔑 O navegador da coleta não tem uma sessão do TikTok — "
     "por isso as buscas voltam vazias. Clique em 🔑 Conectar TikTok, faça login uma "
     "vez, e teste de novo."),
    ("não devolveu nenhum vídeo", "🚫 O TikTok não mostrou nenhum vídeo desta vez. "
     "Clique em 🔑 Conectar TikTok para fazer login e tente de novo."),
    ("Failed to establish a new connection", "🌐 Sem conexão com a internet, ou o serviço "
                                             "está fora do ar. Tente de novo em alguns minutos."),
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
  button.principal { background:var(--grad); border-color:transparent; color:#fff;
                     box-shadow:0 8px 22px -10px rgba(131,58,180,.55) }
  button.principal:hover:not(:disabled) { filter:brightness(1.07); color:#fff }
  button:disabled { opacity:.45; cursor:not-allowed }
  button:focus-visible, a.btn:focus-visible, select:focus-visible {
    outline:2px solid var(--rosa); outline-offset:2px }
  select { font:inherit; font-size:.85rem; padding:9px 14px; border-radius:999px;
           border:1.5px solid var(--borda); background:var(--painel); color:var(--tinta);
           cursor:pointer }

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
        <span class="icone">🔄</span>
        <div>
          <b>Atualizar programa</b>
          <p>Baixa a versão mais recente, com as correções e melhorias.</p>
        </div>
        <button id="atualizarPrograma">Atualizar</button>
      </li>
    </ul>
  </section>

  <div id="log"></div>
  <p class="rodape">💡 Pode deixar esta aba aberta enquanto trabalha — o progresso
     aparece aqui. A janela preta precisa continuar aberta: é ela que faz o trabalho.</p>
</div>
<script>
const $ = s => document.querySelector(s);
const ACOES = { gerar:'/gerar', testar:'/testar', publicar:'/publicar',
                conectarTiktok:'/tiktok-login', atualizarPrograma:'/atualizar' };
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
    const alvo = id === 'gerar' || id === 'testar'
      ? rota + '?nicho=' + encodeURIComponent($('#nicho').value) : rota;
    await fetch(alvo, {method:'POST'});
    atualizar();
    if (id === 'atualizarPrograma') setTimeout(conferirVersao, 20000);
  };
}

carregarNichos();
conferirChave();
conferirVersao();
setInterval(conferirVersao, 60000);
atualizar();
setInterval(atualizar, 1500);
</script></body></html>
"""


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
        caminho = self.path.split("?")[0]
        if caminho == "/":
            self._responder(PAGINA.encode("utf-8"))
        elif caminho == "/nichos":
            self._json({"nichos": _nichos()})
        elif caminho == "/versao":
            self._json(versao_cache)
        elif caminho == "/chaves":
            self._json({"anthropic": _tem_chave()})
        elif caminho == "/status":
            with trava:
                self._json({**estado, "agenda": _info_agenda()})
        elif caminho == "/agenda":
            arquivo = RAIZ / "web" / "index.html"
            if arquivo.exists():
                self._responder(arquivo.read_bytes())
            else:
                self._responder(b"Nenhuma agenda gerada ainda.", codigo=404)
        else:
            self._responder(b"nao encontrado", codigo=404)

    def do_POST(self) -> None:  # noqa: N802
        caminho, _, consulta = self.path.partition("?")
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
