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
from src.descoberta.tiktok_creative_center import tendencias_tiktok
from src.descoberta.youtube import descobrir_virais
from src.roteiros.gerador import gerar_roteiros

RAIZ = Path(__file__).resolve().parent.parent


def main() -> None:
    load_dotenv(RAIZ / ".env")

    parser = argparse.ArgumentParser(description="Radar de Conteúdo Viral")
    parser.add_argument("--nicho", required=True, help="nome do arquivo em config/nichos/ (sem .yaml)")
    parser.add_argument("--apenas-descoberta", action="store_true",
                        help="só busca os virais, sem gerar roteiros (não gasta tokens de IA)")
    parser.add_argument("--publicar-site", action="store_true",
                        help="além da agenda, atualiza web/index.html com o resultado")
    args = parser.parse_args()

    caminho_config = RAIZ / "config" / "nichos" / f"{args.nicho}.yaml"
    if not caminho_config.exists():
        disponiveis = [p.stem for p in (RAIZ / "config" / "nichos").glob("*.yaml")]
        parser.error(f"nicho '{args.nicho}' não encontrado. Disponíveis: {disponiveis}")

    config = yaml.safe_load(caminho_config.read_text(encoding="utf-8"))
    saida = RAIZ / "saida" / args.nicho / date.today().isoformat()
    saida.mkdir(parents=True, exist_ok=True)

    print(f"🔎 Coletando sinais de tendência do nicho '{config['nome']}'...")
    sinais = {}

    print("   TikTok Creative Center (hashtags em alta)...")
    sinais["tiktok_creative_center"] = tendencias_tiktok(config)

    print("   TikTok — vídeos virais das hashtags do nicho (via Apify)...")
    sinais["tiktok_virais"] = virais_tiktok(config)

    print("   Instagram — top posts das hashtags do nicho (via Apify)...")
    sinais["instagram_virais"] = virais_instagram(config)

    print("   YouTube Shorts — vídeos virais do nicho...")
    sinais["youtube_virais"] = descobrir_virais(config) if os.environ.get("YOUTUBE_API_KEY") else []

    (saida / "sinais.json").write_text(
        json.dumps(sinais, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    total = sum(len(v) for v in sinais.values())
    print(f"   {total} sinais coletados -> {saida / 'sinais.json'}")
    if total == 0:
        print("⚠️  Nenhuma fonte retornou dados. Configure as chaves no .env "
              "(veja o README); a geração ainda funciona com a pesquisa web do "
              "Claude, mas com menos embasamento de dados.")

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
