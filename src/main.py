"""CLI do pipeline: descoberta de virais -> roteiros embasados -> agenda.

Uso:
    python -m src.main --nicho dermatologia-estetica
    python -m src.main --nicho dermatologia-estetica --apenas-descoberta
"""

import argparse
import json
from datetime import date
from pathlib import Path

import yaml
from dotenv import load_dotenv

from src.agenda.montador import montar_agenda
from src.descoberta.youtube import descobrir_virais
from src.roteiros.gerador import gerar_roteiros

RAIZ = Path(__file__).resolve().parent.parent


def main() -> None:
    load_dotenv(RAIZ / ".env")

    parser = argparse.ArgumentParser(description="Radar de Conteúdo Viral")
    parser.add_argument("--nicho", required=True, help="nome do arquivo em config/nichos/ (sem .yaml)")
    parser.add_argument("--apenas-descoberta", action="store_true",
                        help="só busca os virais, sem gerar roteiros (não gasta tokens de IA)")
    args = parser.parse_args()

    caminho_config = RAIZ / "config" / "nichos" / f"{args.nicho}.yaml"
    if not caminho_config.exists():
        disponiveis = [p.stem for p in (RAIZ / "config" / "nichos").glob("*.yaml")]
        parser.error(f"nicho '{args.nicho}' não encontrado. Disponíveis: {disponiveis}")

    config = yaml.safe_load(caminho_config.read_text(encoding="utf-8"))
    saida = RAIZ / "saida" / args.nicho / date.today().isoformat()
    saida.mkdir(parents=True, exist_ok=True)

    print(f"🔎 Buscando vídeos virais do nicho '{config['nome']}'...")
    virais = descobrir_virais(config)
    (saida / "virais.json").write_text(
        json.dumps(virais, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"   {len(virais)} virais ranqueados -> {saida / 'virais.json'}")

    if args.apenas_descoberta:
        return

    print("✍️  Gerando ideias e roteiros embasados (isso leva alguns minutos)...")
    roteiros = gerar_roteiros(config, virais)
    (saida / "roteiros.json").write_text(
        json.dumps(roteiros, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"   {len(roteiros['ideias'])} roteiros -> {saida / 'roteiros.json'}")

    print("🗓️  Montando a agenda semanal...")
    agenda = montar_agenda(config, roteiros, virais)
    (saida / "agenda.md").write_text(agenda, encoding="utf-8")
    print(f"✅ Agenda pronta: {saida / 'agenda.md'}")


if __name__ == "__main__":
    main()
