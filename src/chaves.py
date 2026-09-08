"""Conferência da chave da IA, com diagnóstico em vez de erro cru.

Usada antes de qualquer trabalho que dependa da API: a mensagem do SDK
("Could not resolve authentication method") não diz a ninguém o que fazer,
e a coleta que vem antes leva minutos que não se quer perder.
"""

import os
from pathlib import Path


def conferir_anthropic(raiz: Path) -> None:
    """Aborta antes da coleta se a chave da IA não estiver configurada.

    A coleta leva minutos. Descobrir a falta da chave só na hora de
    escrever joga esse tempo fora — e o erro cru do SDK ("Could not
    resolve authentication method") não diz a ninguém o que fazer.
    """
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return

    env = raiz / ".env"
    print("❌ Falta a chave da Anthropic — sem ela não dá para escrever os roteiros.")
    if not env.exists():
        # No Windows o Bloco de Notas salva ".env" como ".env.txt" sem avisar
        disfarcados = [p.name for p in raiz.glob(".env*")
                       if p.name not in (".env", ".env.example")]
        if disfarcados:
            print(f"   Encontrei {disfarcados[0]} na pasta — o Windows renomeou o "
                  "arquivo ao salvar.")
            print(f'   Renomeie {disfarcados[0]} para .env (com o ponto, sem .txt).')
        else:
            print("   O arquivo .env não existe nesta pasta.")
    elif "ANTHROPIC_API_KEY" not in env.read_text(encoding="utf-8", errors="ignore"):
        print("   O arquivo .env existe, mas não tem a linha ANTHROPIC_API_KEY.")
    else:
        print("   A linha ANTHROPIC_API_KEY existe no .env, mas está vazia.")

    print("\n   Jeito mais fácil de resolver: abra o painel (abrir-painel) e cole a")
    print("   chave no campo que aparece — ele cria o arquivo do jeito certo.")
    print("   A chave fica em console.anthropic.com → Settings → API keys.")
    raise SystemExit(1)
