"""CLI do pipeline: descoberta de virais -> roteiros embasados -> agenda.

Uso:
    python -m src.main --nicho dermatologia-estetica
    python -m src.main --nicho dermatologia-estetica --apenas-descoberta
"""

import argparse
import json
import os
from datetime import date
from pathlib import Path

import yaml
from dotenv import load_dotenv

from src.agenda.montador import montar_agenda
from src.historico import carregar_historico, registrar_historico
from src.descoberta.apify_social import virais_instagram, virais_tiktok
from src.descoberta.tiktok_local import virais_tiktok_local
from src.descoberta.youtube import descobrir_virais
from src.roteiros.gerador import gerar_roteiros

RAIZ = Path(__file__).resolve().parent.parent


def _conferir_chave() -> None:
    """Aborta antes da coleta se a chave da IA não estiver configurada.

    A coleta leva minutos. Descobrir a falta da chave só na hora de
    escrever joga esse tempo fora — e o erro cru do SDK ("Could not
    resolve authentication method") não diz a ninguém o que fazer.
    """
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return

    env = RAIZ / ".env"
    print("❌ Falta a chave da Anthropic — sem ela não dá para escrever os roteiros.")
    if not env.exists():
        # No Windows o Bloco de Notas salva ".env" como ".env.txt" sem avisar
        disfarcados = [p.name for p in RAIZ.glob(".env*")
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


def main() -> None:
    load_dotenv(RAIZ / ".env")

    parser = argparse.ArgumentParser(description="Radar de Conteúdo Viral")
    parser.add_argument("--nicho", required=True, help="nome do arquivo em config/nichos/ (sem .yaml)")
    parser.add_argument("--apenas-descoberta", action="store_true",
                        help="só busca os virais, sem gerar roteiros (não gasta tokens de IA)")
    parser.add_argument("--publicar-site", action="store_true",
                        help="além da agenda, atualiza web/index.html com o resultado")
    parser.add_argument("--coleta", choices=("auto", "local", "apify"), default="auto",
                        help="auto: tenta a coleta local (grátis) e usa o Apify se faltar; "
                             "local: só o navegador desta máquina; apify: só o serviço pago")
    args = parser.parse_args()

    caminho_config = RAIZ / "config" / "nichos" / f"{args.nicho}.yaml"
    if not caminho_config.exists():
        disponiveis = [p.stem for p in (RAIZ / "config" / "nichos").glob("*.yaml")]
        parser.error(f"nicho '{args.nicho}' não encontrado. Disponíveis: {disponiveis}")

    if not args.apenas_descoberta:
        _conferir_chave()  # antes da coleta: ela leva minutos

    config = yaml.safe_load(caminho_config.read_text(encoding="utf-8"))
    saida = RAIZ / "saida" / args.nicho / date.today().isoformat()
    saida.mkdir(parents=True, exist_ok=True)

    print(f"🔎 Coletando sinais de tendência do nicho '{config['nome']}'...")
    sinais = {}
    tem_apify = bool(os.environ.get("APIFY_API_TOKEN"))

    if args.coleta in ("auto", "local"):
        print("   TikTok — coleta local pelo seu navegador (grátis, sem cota)...")
        sinais["tiktok_virais"] = virais_tiktok_local(config)
        print(f"   → {len(sinais['tiktok_virais'])} vídeos coletados localmente")

    poucos = len(sinais.get("tiktok_virais", [])) < 5
    if args.coleta == "apify" or (args.coleta == "auto" and poucos and tem_apify):
        if poucos and args.coleta == "auto":
            print("   Coleta local trouxe pouca coisa — usando o Apify como reserva...")
        sinais["tiktok_virais"] = virais_tiktok(config) or sinais.get("tiktok_virais", [])
        print("   Instagram — top posts das hashtags do nicho (via Apify)...")
        sinais["instagram_virais"] = virais_instagram(config)

    print("   YouTube Shorts — vídeos virais do nicho (API oficial, grátis)...")
    sinais["youtube_virais"] = descobrir_virais(config) if os.environ.get("YOUTUBE_API_KEY") else []

    (saida / "sinais.json").write_text(
        json.dumps(sinais, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    total = sum(len(v) for v in sinais.values())
    print(f"   {total} sinais coletados -> {saida / 'sinais.json'}")
    if total == 0 and not args.apenas_descoberta:
        raise SystemExit(
            "❌ Nenhum sinal coletado — a metodologia exige virais reais como "
            "origem das ideias, então a geração foi abortada antes de gastar "
            "com a IA.\n   Causas comuns: instabilidade do Apify (tente de novo "
            "em alguns minutos) ou APIFY_API_TOKEN ausente/inválido."
        )

    if args.apenas_descoberta:
        return

    historico = carregar_historico(RAIZ, args.nicho)
    if historico:
        print(f"🧠 Memória: {len(historico)} ideias já publicadas — não serão repetidas")
    print("✍️  Gerando ideias e roteiros embasados (isso leva alguns minutos)...")
    roteiros = gerar_roteiros(config, sinais, historico)
    (saida / "roteiros.json").write_text(
        json.dumps(roteiros, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"   {len(roteiros['ideias'])} roteiros -> {saida / 'roteiros.json'}")

    print("🗓️  Montando a agenda semanal...")
    agenda = montar_agenda(config, roteiros, sinais)
    (saida / "agenda.md").write_text(agenda, encoding="utf-8")
    print(f"✅ Agenda pronta: {saida / 'agenda.md'}")

    if args.publicar_site:
        from src.publicar.site import publicar_agenda
        destino = publicar_agenda(config, roteiros, sinais, RAIZ)
        # persiste a geração para permitir re-render (mudança de design)
        # sem custo de IA — ver src/publicar/rerender.py
        dados_dir = RAIZ / "dados"
        dados_dir.mkdir(exist_ok=True)
        (dados_dir / f"{args.nicho}.json").write_text(
            json.dumps({"roteiros": roteiros, "sinais": sinais},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        total_hist = registrar_historico(RAIZ, args.nicho, roteiros)
        print(f"🧠 Histórico atualizado ({total_hist} ideias acumuladas)")
        print(f"🌐 Site atualizado: {destino}")


if __name__ == "__main__":
    main()
