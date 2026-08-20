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


def main() -> int:
    if not (RAIZ / "web" / "index.html").exists():
        print("❌ Nenhuma agenda encontrada. Gere a agenda antes de publicar.")
        return 1

    _git("add", "web", "dados")
    if _git("diff", "--cached", "--quiet").returncode == 0:
        print("ℹ️  Nada novo para publicar — o site já está atualizado.")
        return 0

    commit = _git("commit", "-m", f"chore: agenda de {date.today().strftime('%d/%m/%Y')}")
    if commit.returncode != 0:
        print(f"❌ Não consegui salvar as alterações:\n{commit.stdout}{commit.stderr}")
        return 1
    print("📦 Alterações salvas.")

    print("☁️  Enviando para o GitHub...")
    envio = _git("push")
    if envio.returncode != 0:
        print(f"❌ Falha ao enviar:\n{envio.stdout}{envio.stderr}\n"
              "Dica: verifique sua conexão e se o Git está autenticado nesta máquina.")
        return 1

    print("✅ Publicado! O site atualiza em cerca de 1 minuto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
