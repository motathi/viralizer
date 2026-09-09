"""Re-renderiza o site a partir da última geração persistida (sem custo de IA).

Uso: python -m src.publicar.rerender --nicho dermatologia-estetica

Permite atualizar o design/estrutura da página sem gerar roteiros de novo:
o pipeline salva os dados de cada geração em dados/<nicho>.json e este
comando reconstrói web/index.html a partir deles.
"""

import argparse
import json
from pathlib import Path

import yaml

from src.publicar.site import publicar_agenda

RAIZ = Path(__file__).resolve().parent.parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-renderiza o site da agenda")
    parser.add_argument("--nicho", required=True)
    args = parser.parse_args()

    config = yaml.safe_load(
        (RAIZ / "config" / "nichos" / f"{args.nicho}.yaml").read_text(encoding="utf-8")
    )
    dados = json.loads(
        (RAIZ / "dados" / f"{args.nicho}.json").read_text(encoding="utf-8")
    )
    destino = publicar_agenda(config, dados["roteiros"], dados["sinais"], RAIZ,
                              nicho=args.nicho)
    print(f"🌐 Site re-renderizado: {destino}")


if __name__ == "__main__":
    main()
