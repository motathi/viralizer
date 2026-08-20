"""Baixa a versão mais recente do programa, preservando o trabalho local.

Usado pelo botão "🔄 Atualizar agora" do painel. Usa --autostash, então
agendas geradas e ainda não publicadas são guardadas e reaplicadas depois
da atualização.
"""

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent


def main() -> int:
    if not (RAIZ / ".git").exists():
        print("❌ Esta pasta foi baixada como ZIP e não recebe atualizações.")
        print("   Para atualizar com um clique daqui em diante, baixe uma única vez com:")
        print("   git clone <endereço do repositório>")
        return 1

    print("🔄 Buscando a versão mais recente...")
    r = subprocess.run(["git", "pull", "--rebase", "--autostash"], cwd=RAIZ,
                       capture_output=True, text=True, check=False)
    saida = (r.stdout + r.stderr).strip()
    print(saida)

    if r.returncode != 0:
        if "conflict" in saida.lower():
            print("\n⚠️  Suas alterações locais conflitam com a versão nova.")
            print("   Publique o que você gerou (botão ☁️ Publicar) e tente de novo.")
        else:
            print("\n⚠️  Não consegui atualizar. Verifique sua conexão com a internet.")
        return 1

    print("\n📦 Conferindo se há novos programas de apoio...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"],
                   cwd=RAIZ, check=False)

    print("✅ Atualizado! Feche esta janela e abra o painel de novo para usar a versão nova.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
