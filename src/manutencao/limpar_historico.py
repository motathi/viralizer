"""Remove do histórico do git os commits do projeto antigo (NFT).

Uso único. O que faz, nesta ordem:

1. Baixa uma cópia nova do repositório numa pasta temporária (nunca mexe
   na sua pasta de trabalho durante a reescrita).
2. Reconstrói, um a um, os commits posteriores à limpeza: mesma árvore de
   arquivos, mesmo autor, mesma data, mesma mensagem — só os pais são
   religados, e o primeiro commit útil ("feat: pipeline de radar...") fica
   sem pai. Os três commits do NFT (inicial, limpeza e merge #1) deixam de
   existir na ancestralidade, e com eles os 262 arquivos antigos.
   (Feito com os comandos de baixo nível do git, sem ferramenta externa:
   git-filter-repo e git-filter-branch ignoraram o corte nos testes.)
3. Confere que a ÁRVORE final é byte a byte idêntica à atual. Se um único
   arquivo tiver mudado, para aqui e não envia nada.
4. Envia o histórico novo para o GitHub com --force-with-lease (só aceita
   se ninguém tiver publicado no meio-tempo).
5. Alinha a sua pasta de trabalho ao histórico novo (git reset --hard).
   Arquivos não rastreados — .env, dados locais, o navegador da coleta —
   ficam como estão. Alterações rastreadas e não publicadas seriam
   perdidas, por isso o script se recusa a rodar se houver alguma.

Uso:
    python -m src.manutencao.limpar_historico            # faz tudo
    python -m src.manutencao.limpar_historico --simular  # só os passos 1 a 3
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
NOVA_RAIZ = "b86b4e7"  # feat: pipeline de radar de conteúdo viral para nichos de saúde
RAMO = "master"
# Ramos que ainda alcançam o histórico antigo e já estão inteiros no master
RAMOS_OBSOLETOS = ("claude/limpar-repositorio-3y5aif", "claude/online-tools-frontend-7f17gm")


def _git(*args: str, cwd: Path = RAIZ, check: bool = True, entrada: str | None = None,
         env: dict | None = None) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=False,
                       input=entrada, env=env)
    if check and r.returncode != 0:
        raise SystemExit(f"❌ git {' '.join(args)} falhou:\n{r.stdout}{r.stderr}")
    return r.stdout.strip()


def _ler_commit(sha: str, cwd: Path) -> tuple[str, dict, str]:
    """Árvore, cabeçalhos (author/committer) e mensagem de um commit."""
    bruto = subprocess.run(["git", "cat-file", "commit", sha], cwd=cwd, capture_output=True,
                           check=True).stdout.decode("utf-8", "surrogateescape")
    cabecalho, _, mensagem = bruto.partition("\n\n")
    campos: dict[str, str] = {}
    for linha in cabecalho.splitlines():
        if linha.startswith(" "):  # continuação (ex.: assinatura gpg) — descartada
            continue
        chave, _, valor = linha.partition(" ")
        if chave in ("author", "committer", "tree"):
            campos[chave] = valor
    return campos["tree"], campos, mensagem


def _ambiente(campos: dict) -> dict:
    """Autor e data originais viram variáveis para o commit-tree reproduzir."""
    env = dict(os.environ)
    for papel, prefixo in (("author", "GIT_AUTHOR"), ("committer", "GIT_COMMITTER")):
        pessoa, _, data = campos[papel].rpartition("> ")
        nome, _, email = pessoa.partition(" <")
        env[f"{prefixo}_NAME"] = nome
        env[f"{prefixo}_EMAIL"] = email
        env[f"{prefixo}_DATE"] = data
    return env


def _reconstruir(copia: Path) -> tuple[str, int]:
    """Recria os commits de NOVA_RAIZ até RAMO com a raiz sem pais. Devolve (sha novo, quantidade)."""
    raiz = _git("rev-parse", NOVA_RAIZ, cwd=copia)
    pai_da_raiz = _git("rev-parse", f"{NOVA_RAIZ}^", cwd=copia)
    linhas = _git("rev-list", "--reverse", "--topo-order", "--parents",
                  f"{pai_da_raiz}..{RAMO}", cwd=copia).splitlines()
    novos: dict[str, str] = {}
    for linha in linhas:
        sha, *pais = linha.split()
        # Todo laço com o commit de limpeza é cortado — não só o da raiz
        # principal: mais de um ramo partiu dele, e cada um vira uma raiz.
        pais_uteis = [p for p in pais if p != pai_da_raiz]
        faltando = [p for p in pais_uteis if p not in novos]
        if faltando:
            raise SystemExit(f"❌ O commit {sha[:10]} tem um pai fora do histórico novo "
                             f"({faltando[0][:10]}). Nada foi enviado. Me mostre esta mensagem.")
        pais_novos = [novos[p] for p in pais_uteis]
        arvore, campos, mensagem = _ler_commit(sha, copia)
        args = ["commit-tree", arvore]
        for p in pais_novos:
            args += ["-p", p]
        novos[sha] = _git(*args, cwd=copia, entrada=mensagem, env=_ambiente(campos))
    ponta = _git("rev-parse", RAMO, cwd=copia)
    return novos[ponta], len(novos)


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove o projeto antigo do histórico do git")
    parser.add_argument("--simular", action="store_true",
                        help="baixa, reescreve na cópia e confere — mas não envia nem mexe aqui")
    args = parser.parse_args()

    if not (RAIZ / ".git").exists():
        raise SystemExit("❌ Esta pasta não é um clone do git.")
    if _git("status", "--porcelain", "--untracked-files=no"):
        raise SystemExit("❌ Há alterações não publicadas nesta pasta. Clique em Publicar no "
                         "painel (ou desfaça as alterações) e rode de novo.")

    url = _git("remote", "get-url", "origin")
    _git("fetch", "-q", "origin", RAMO)
    antigo = _git("rev-parse", f"origin/{RAMO}")
    arvore = _git("rev-parse", f"origin/{RAMO}^{{tree}}")
    print(f"🔎 {RAMO} atual: {antigo[:10]} · árvore {arvore[:10]}")
    if _git("cat-file", "-t", NOVA_RAIZ, check=False) != "commit":
        raise SystemExit(f"❌ Não encontrei o commit {NOVA_RAIZ} — o histórico já foi reescrito?")

    temporaria = Path(tempfile.mkdtemp(prefix="radar-historico-"))
    copia = temporaria / "repo"
    try:
        print("⬇️  Baixando uma cópia nova para reescrever...")
        _git("clone", "-q", "--no-local", url, str(copia), cwd=temporaria)
        _git("checkout", "-q", RAMO, cwd=copia)
        antes = int(_git("rev-list", "--count", RAMO, cwd=copia))

        print(f"✂️  Reconstruindo o histórico a partir de {NOVA_RAIZ}...")
        ponta_nova, depois = _reconstruir(copia)
        _git("update-ref", f"refs/heads/{RAMO}", ponta_nova, cwd=copia)
        _git("remote", "remove", "origin", cwd=copia)  # as refs remotas ainda apontavam ao antigo
        _git("reflog", "expire", "--expire=now", "--all", cwd=copia)
        _git("gc", "-q", "--prune=now", cwd=copia)

        raiz_nova = _git("log", "--reverse", "--format=%h %s", RAMO, cwd=copia).splitlines()[0]
        sobras = subprocess.run("git rev-list --objects --all | grep -c 'public/\\|\\.babelrc'",
                                shell=True, cwd=copia, capture_output=True, text=True).stdout.strip() or "0"
        print(f"   commits: {antes} → {depois} · nova raiz: {raiz_nova}")
        print(f"   objetos do projeto antigo ainda alcançáveis: {sobras}")
        if depois >= antes:
            raise SystemExit("❌ O histórico não encolheu — o corte não aconteceu. Nada foi enviado. "
                             "Me mostre esta mensagem.")

        nova = _git("rev-parse", f"{RAMO}^{{tree}}", cwd=copia)
        if nova != arvore:
            raise SystemExit(f"❌ A árvore final ({nova[:10]}) NÃO é idêntica à atual ({arvore[:10]}). "
                             "Nada foi enviado. Me mostre esta mensagem.")
        print("✅ Árvore final idêntica à atual — nenhum arquivo mudou.")

        if args.simular:
            print(f"   (no envio real, também retiraria do GitHub os ramos: {', '.join(RAMOS_OBSOLETOS)})")
            print("\n🧪 Simulação: parando aqui. Nada foi enviado e nada mudou nesta pasta.")
            return 0

        print("☁️  Enviando o histórico novo para o GitHub...")
        _git("remote", "add", "origin", url, cwd=copia)
        _git("push", "-q", f"--force-with-lease=refs/heads/{RAMO}:{antigo}", "origin", RAMO, cwd=copia)
        print("✅ Enviado.")

        # Objeto só some do GitHub quando NENHUM ramo o alcança. Estes dois
        # ainda apontam para o histórico antigo e já estão inteiros no master
        # (conferido em 11/09/2026 — o segundo está no mesmo commit do master).
        for ramo in RAMOS_OBSOLETOS:
            r = subprocess.run(["git", "push", "-q", "origin", "--delete", ramo], cwd=copia,
                               capture_output=True, text=True)
            print(f"   🧹 ramo {ramo}: {'apagado do GitHub' if r.returncode == 0 else 'já não existia'}")
    finally:
        shutil.rmtree(temporaria, ignore_errors=True)

    print("🔁 Alinhando esta pasta ao histórico novo...")
    _git("fetch", "-q", "origin", RAMO)
    _git("checkout", "-q", RAMO)
    _git("reset", "-q", "--hard", f"origin/{RAMO}")
    _git("reflog", "expire", "--expire=now", "--all")
    _git("gc", "-q", "--prune=now")
    print(f"✅ Pronto. Histórico com {_git('rev-list', '--count', RAMO)} commits; "
          "o projeto antigo não existe mais no git.")
    print("   Observação: o GitHub ainda pode mostrar os commits antigos por endereço direto por "
          "algum tempo (cache). Para apagar até isso, é pedido ao suporte do GitHub.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
