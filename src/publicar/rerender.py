"""Re-renderiza o site a partir da última geração persistida (sem custo de IA).

Uso: python -m src.publicar.rerender --nicho dermatologia-estetica

Permite atualizar o design/estrutura das páginas sem gerar roteiros de novo:
o pipeline salva os dados de cada geração em dados/<nicho>.json e este
comando reconstrói web/ a partir deles — a agenda, o arquivo da semana e
as páginas de ferramentas (estúdio, galeria, manual, ferramentas).

A semana e a data de geração são preservadas: re-renderizar uma agenda
antiga não a faz parecer nova nem cria um arquivo de semana a mais.
"""

import argparse
import json
import re
from pathlib import Path

import yaml

from src.publicar.site import publicar_agenda

RAIZ = Path(__file__).resolve().parent.parent.parent


def _semana_publicada(raiz: Path) -> tuple[str | None, str | None]:
    """Semana e data de geração da agenda que está no ar (gerações antigas
    não guardavam isso em dados/, mas a página publicada guarda)."""
    pagina = raiz / "web" / "index.html"
    if not pagina.exists():
        return None, None
    texto = pagina.read_text(encoding="utf-8")
    semana = re.search(r'"semana":\s*"(\d{4}-\d{2}-\d{2})"', texto)
    gerado = re.search(r'"gerado_em":\s*"(\d{4}-\d{2}-\d{2})"', texto)
    return (semana.group(1) if semana else None), (gerado.group(1) if gerado else None)


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
    semana, gerado_em = dados.get("semana"), dados.get("gerado_em")
    if not semana or not gerado_em:
        semana_site, gerado_site = _semana_publicada(RAIZ)
        semana, gerado_em = semana or semana_site, gerado_em or gerado_site
    destino = publicar_agenda(config, dados["roteiros"], dados["sinais"], RAIZ,
                              nicho=args.nicho, semana=semana, gerado_em=gerado_em)
    print(f"🌐 Site re-renderizado: {destino} (semana {semana or 'nova'})")


if __name__ == "__main__":
    main()
