"""Painel local: gere a agenda da semana com um clique, na sua máquina.

Sobe um servidor em http://127.0.0.1:8777 (só acessível neste computador) e
abre o navegador com um painel de botões:

- ▶ Gerar agenda desta semana — roda o pipeline completo aqui, pelo seu IP
- 👀 Abrir agenda — abre o resultado no navegador
- ☁️ Publicar no site — envia para o GitHub (a Vercel publica sozinha)

Uso: dê um duplo clique em abrir-painel.bat (Windows), abrir-painel.command
(Mac) ou abrir-painel.sh (Linux). Ou rode: python -m src.painel.servidor
"""

import json
import os
import subprocess
import sys
import threading
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
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  :root { --grad: linear-gradient(45deg,#405DE6,#833AB4 30%,#C13584 50%,#E1306C 70%,#F77737);
          --tinta:#262626; --suave:#737373; --borda:#efefef; --ok:#1f9d63; }
  * { box-sizing:border-box; margin:0 }
  body { font-family:Inter,"Segoe UI",system-ui,sans-serif; background:#fff; color:var(--tinta);
         line-height:1.6; padding:32px 18px; }
  .wrap { max-width:760px; margin:0 auto }
  h1 { font-size:1.6rem; font-weight:800; letter-spacing:-.02em }
  h1 span { background:var(--grad); -webkit-background-clip:text; background-clip:text;
            -webkit-text-fill-color:transparent }
  .sub { color:var(--suave); font-size:.92rem; margin-top:6px }
  .status { display:flex; gap:10px; align-items:center; background:#fafafa;
            border:1px solid var(--borda); border-radius:14px; padding:14px 18px; margin:22px 0 }
  .status b { color:var(--tinta) }
  .botoes { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:18px }
  button, a.btn { font:inherit; font-size:.95rem; font-weight:700; padding:14px 22px;
                  border-radius:999px; border:1.5px solid var(--borda); background:#fff;
                  color:var(--tinta); cursor:pointer; transition:all .2s; text-decoration:none;
                  display:inline-block }
  button:hover:not(:disabled), a.btn:hover { border-color:#C13584; color:#C13584 }
  button.principal { background:var(--grad); border-color:transparent; color:#fff;
                     box-shadow:0 8px 24px -8px rgba(131,58,180,.4) }
  button.principal:hover:not(:disabled) { filter:brightness(1.07); color:#fff }
  button:disabled { opacity:.5; cursor:not-allowed }
  select { font:inherit; padding:13px 18px; border-radius:999px; border:1.5px solid var(--borda);
           background:#fafafa; cursor:pointer }
  #log { background:#1d1a20; color:#f0eaf2; font-family:ui-monospace,Menlo,Consolas,monospace;
         font-size:.82rem; line-height:1.55; border-radius:14px; padding:16px 18px;
         white-space:pre-wrap; max-height:420px; overflow-y:auto; display:none }
  #log.visivel { display:block }
  .dica { color:var(--suave); font-size:.85rem; margin-top:18px }
  .girando { display:inline-block; width:14px; height:14px; border:2px solid #ddd;
             border-top-color:#C13584; border-radius:50%; animation:g .8s linear infinite }
  @keyframes g { to { transform:rotate(360deg) } }
</style></head><body><div class="wrap">
  <h1>Painel do <span>Radar de Conteúdo Viral</span></h1>
  <p class="sub">Tudo roda neste computador. Clique no botão e aguarde alguns minutos.</p>

  <div class="status" id="status">carregando…</div>

  <div class="botoes">
    <select id="nicho"></select>
    <button class="principal" id="gerar">▶ Gerar agenda desta semana</button>
    <a class="btn" id="abrir" href="/agenda" target="_blank">👀 Abrir agenda</a>
    <button id="publicar">☁️ Publicar no site</button>
  </div>

  <div id="log"></div>
  <p class="dica">💡 A geração leva de 5 a 10 minutos. Pode deixar esta aba aberta —
  o progresso aparece aqui embaixo.</p>
</div>
<script>
const $ = s => document.querySelector(s);
let rodando = false;

async function carregarNichos() {
  const r = await (await fetch('/nichos')).json();
  $('#nicho').innerHTML = r.nichos.map(n => `<option value="${n}">${n.replace(/-/g,' ')}</option>`).join('');
}

function pintar(e) {
  rodando = e.rodando;
  $('#gerar').disabled = e.rodando;
  $('#publicar').disabled = e.rodando;
  const s = $('#status');
  if (e.rodando) {
    s.innerHTML = `<span class="girando"></span> <b>${e.acao}</b> — em andamento…`;
  } else if (e.agenda.quando) {
    const fim = e.fim ? ` · última ação às ${e.fim}${e.erro ? ' (com erro)' : ''}` : '';
    s.innerHTML = `📅 Agenda com <b>${e.agenda.ideias} ideias</b>, gerada em <b>${e.agenda.quando}</b>${fim}`;
  } else {
    s.innerHTML = 'Nenhuma agenda gerada ainda — clique em <b>Gerar agenda</b>.';
  }
  if (e.log.length) {
    const l = $('#log');
    const colado = l.scrollTop + l.clientHeight >= l.scrollHeight - 30;
    l.textContent = e.log.join('\\n');
    l.classList.add('visivel');
    if (colado) l.scrollTop = l.scrollHeight;
  }
}

async function atualizar() {
  try { pintar(await (await fetch('/status')).json()); } catch (_) {}
}

$('#gerar').onclick = async () => {
  await fetch('/gerar?nicho=' + encodeURIComponent($('#nicho').value), {method:'POST'});
  atualizar();
};
$('#publicar').onclick = async () => {
  await fetch('/publicar', {method:'POST'});
  atualizar();
};

carregarNichos();
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
