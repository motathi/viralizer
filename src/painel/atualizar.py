"""Baixa a versão mais recente do programa, preservando o trabalho local.

Usado pelo botão "🔄 Atualizar programa" do painel. Usa --autostash, então
agendas geradas e ainda não publicadas são guardadas e reaplicadas depois
da atualização.
"""

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent


def _git(*args, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True,
                          text=True, check=False, **kwargs)


def _ramo_atual() -> str:
    return _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "master"


def _tem_par_no_servidor() -> bool:
    return _git("rev-parse", "--abbrev-ref", "@{u}").returncode == 0


def _versao_curta() -> str:
    return _git("log", "-1", "--format=%h %s").stdout.strip()


def _historico_foi_reescrito(ramo: str) -> bool:
    """O servidor tem um histórico sem ancestral comum com o nosso?

    Acontece uma vez, depois da faxina que tirou o projeto antigo do git:
    cada commit ganhou identidade nova. Um pull --rebase nessa situação
    tenta reaplicar dezenas de commits e trava em conflito.
    """
    _git("fetch", "--quiet", "origin", ramo)
    return _git("merge-base", "HEAD", f"origin/{ramo}").returncode != 0


def _alinhar_ao_servidor(ramo: str) -> int:
    """Troca o histórico local pelo do servidor, guardando o que não foi publicado."""
    print("🧭 O histórico no servidor foi reescrito (faxina do projeto antigo).")
    print("   Vou alinhar esta pasta a ele — seus arquivos locais ficam como estão.")
    sujo = bool(_git("status", "--porcelain", "--untracked-files=no").stdout.strip())
    if sujo:
        _git("stash", "push", "--quiet", "-m", "guardado antes de alinhar ao servidor")
    r = _git("reset", "--hard", f"origin/{ramo}")
    if r.returncode != 0:
        print(f"❌ Não consegui alinhar:\n{r.stdout}{r.stderr}")
        return 1
    if sujo:
        volta = _git("stash", "pop", "--quiet")
        if volta.returncode != 0:
            print("⚠️  Suas alterações não publicadas ficaram guardadas (git stash). "
                  "Me avise para recuperá-las.")
    print(f"✅ Alinhado. Versão atual: {_versao_curta()}")
    return 0


def main() -> int:
    if not (RAIZ / ".git").exists():
        print("❌ Esta pasta foi baixada como ZIP e não recebe atualizações.")
        print("   Para atualizar com um clique daqui em diante, baixe uma única vez com:")
        print("   git clone <endereço do repositório>")
        return 1

    ramo = _ramo_atual()
    antes = _git("rev-parse", "HEAD").stdout.strip()
    print(f"🔄 Buscando a versão mais recente (ramo {ramo})...")
    print(f"   Versão atual: {_versao_curta()}")

    if _historico_foi_reescrito(ramo):
        codigo = _alinhar_ao_servidor(ramo)
        if codigo == 0:
            print("\n📦 Conferindo se há novos programas de apoio...")
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"],
                           cwd=RAIZ, check=False)
            print("\n✅ Atualizado! Feche esta janela e abra o painel de novo para usar a versão nova.")
        return codigo

    comando = ["pull", "--rebase", "--autostash"]
    if not _tem_par_no_servidor():
        # clone antigo ou ramo criado à mão: puxa direto do servidor
        print("   (esta cópia não tinha par no servidor — puxando de origin)")
        comando += ["origin", ramo]

    r = _git(*comando)
    saida = (r.stdout + r.stderr).strip()
    print(saida)

    if r.returncode != 0:
        baixo = saida.lower()
        if "conflict" in baixo:
            print("\n⚠️  Suas alterações locais conflitam com a versão nova.")
            print("   Publique o que você gerou (botão ☁️ Publicar) e tente de novo.")
        elif "authentication" in baixo or "could not read" in baixo or "403" in baixo:
            print("\n🔐 O GitHub pediu login e ninguém respondeu.")
            print("   Abra a janela preta do painel e rode uma vez, na pasta do projeto:")
            print("       git pull")
            print("   Faça o login que aparecer — depois disso o botão funciona sozinho.")
        elif "couldn't find remote ref" in baixo or "no such ref" in baixo:
            print(f"\n⚠️  O ramo '{ramo}' não existe no servidor.")
            print("   Rode uma vez na pasta do projeto: git checkout master")
        else:
            print("\n⚠️  Não consegui atualizar. Verifique sua conexão com a internet.")
        return 1

    depois = _git("rev-parse", "HEAD").stdout.strip()
    if antes == depois:
        print("\n✅ Você já está na versão mais recente — nada a baixar.")
        return 0

    novidades = _git("log", "--oneline", f"{antes}..{depois}").stdout.strip()
    if novidades:
        print(f"\n📋 O que chegou:\n{novidades}")

    print("\n📦 Conferindo se há novos programas de apoio...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check",
                    "-r", "requirements.txt"],
                   cwd=RAIZ, check=False)

    print("\n✅ Atualizado! Feche esta janela e abra o painel de novo para usar a versão nova.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
