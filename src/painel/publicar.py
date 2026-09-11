"""Envia a agenda gerada para o GitHub (a Vercel publica em seguida).

Usado pelo botão "☁️ Publicar no site" do painel local.
"""

import subprocess
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=RAIZ, text=True,
                          capture_output=True, check=False)


def _garantir_identidade() -> None:
    """Sem nome e e-mail o Git recusa o commit — e o site nunca atualiza.

    Numa máquina recém-instalada isso é o normal. Gravamos uma identidade
    só neste repositório (sem --global), para não mexer em nada fora dele.
    """
    if _git("config", "user.email").stdout.strip() and _git("config", "user.name").stdout.strip():
        return
    _git("config", "user.name", "Radar de Conteúdo Viral")
    _git("config", "user.email", "radar@painel.local")
    print("🪪 Identidade do Git configurada neste projeto (só para os commits do painel).")


def main() -> int:
    if not (RAIZ / "web" / "index.html").exists():
        print("❌ Nenhuma agenda encontrada. Gere a agenda antes de publicar.")
        return 1

    _git("add", "web", "dados")
    if _git("diff", "--cached", "--quiet").returncode == 0:
        print("ℹ️  Nada novo para publicar — o site já está atualizado.")
        return 0

    _garantir_identidade()
    commit = _git("commit", "-m", f"chore: agenda de {date.today().strftime('%d/%m/%Y')}")
    if commit.returncode != 0:
        print(f"❌ Não consegui salvar as alterações:\n{commit.stdout}{commit.stderr}")
        return 1
    print("📦 Alterações salvas.")

    print("☁️  Enviando para o GitHub...")
    _git("fetch", "--quiet", "origin")
    if _git("merge-base", "HEAD", "@{u}").returncode != 0:
        # servidor com histórico reescrito: rebasear travaria em conflito.
        # O commit de agora é reaplicado sozinho sobre o histórico novo.
        print("🧭 O histórico no servidor foi reescrito — reaplicando sua publicação sobre ele.")
        sync = _git("rebase", "--onto", "@{u}", "HEAD~1")
    else:
        sync = _git("pull", "--rebase", "--autostash")
    if sync.returncode != 0:
        print(f"❌ Não consegui juntar com a versão do servidor:\n{sync.stdout}{sync.stderr}")
        return 1
    envio = _git("push", "-u", "origin", "HEAD")
    if envio.returncode != 0:
        print(f"❌ Falha ao enviar:\n{envio.stdout}{envio.stderr}\n"
              "Dica: verifique sua conexão e se o Git está autenticado nesta máquina.")
        return 1

    print("✅ Publicado! O site atualiza em cerca de 1 minuto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
