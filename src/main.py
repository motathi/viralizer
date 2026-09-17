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
from src.chaves import conferir_anthropic
from src.historico import carregar_historico, registrar_historico
from src.descoberta.apify_social import virais_instagram, virais_tiktok
from src.descoberta.rendimento import relatorio
from src.descoberta.termos import registrar as registrar_termos
from src.descoberta.tiktok_local import virais_tiktok_local
from src.descoberta.youtube import descobrir_virais
from src.roteiros.gerador import gerar_roteiros

RAIZ = Path(__file__).resolve().parent.parent


def _chaves_carregadas() -> list[str]:
    """Os NOMES das chaves que o .env trouxe. Nunca os valores."""
    return sorted(n for n in os.environ
                  if n.startswith(("ANTHROPIC_", "APIFY_", "YOUTUBE_", "SUPABASE_", "RADAR_")))


def _raio_x_do_env() -> list[str]:
    """O que existe DENTRO do .env, linha a linha — só nomes, nunca valores.

    Separa três causas que dão o mesmo sintoma: o arquivo não existe (ou tem
    outro nome, como .env.txt), a linha está escrita de um jeito que o leitor
    ignora, ou a linha está certa mas a chave veio do ambiente do Windows e o
    arquivo nem chegou a ser usado.
    """
    env = RAIZ / ".env"
    if not env.exists():
        disfarcados = sorted(p.name for p in RAIZ.glob(".env*")
                             if p.name not in (".env", ".env.example"))
        achado = f" Achei {disfarcados[0]} — renomeie para .env, sem .txt." if disfarcados else ""
        return [f"O arquivo {env} NÃO EXISTE.{achado}"]

    try:
        bruto = env.read_bytes()
    except OSError as e:
        return [f"Não consegui abrir {env}: {e}"]

    saida = [f"Arquivo: {env} ({len(bruto)} bytes)"]
    if bruto.startswith(b"\xff\xfe") or bruto.startswith(b"\xfe\xff"):
        saida.append("⚠️  Está salvo em UTF-16 (opção 'Unicode' do Bloco de Notas). "
                     "O leitor não entende: salve de novo como UTF-8.")
        return saida

    texto = bruto.decode("utf-8", errors="replace").lstrip("\ufeff")
    saida.append("Linhas (só os nomes):")
    for n, linha in enumerate(texto.splitlines(), 1):
        crua = linha.strip()
        if not crua or crua.startswith("#"):
            continue
        if "=" not in crua:
            saida.append(f"  linha {n}: '{crua[:25]}…' — sem '=', o leitor ignora")
            continue
        nome = crua.split("=", 1)[0].removeprefix("export ").strip()
        limpo = "".join(c for c in nome if c.isalnum() or c == "_")
        if limpo != nome:
            saida.append(f"  linha {n}: {limpo} — tem caractere estranho no nome "
                         "(espaço, acento ou invisível colado no copiar/colar)")
        elif os.environ.get(nome, "").strip():
            saida.append(f"  linha {n}: {nome} ✓ chegou")
        else:
            saida.append(f"  linha {n}: {nome} ✗ NÃO chegou — reescreva esta linha à mão")
    return saida


def _virais_youtube(config: dict) -> list:
    """O YouTube nunca derruba a rodada — mas também nunca falha calado.

    Antes isto era um `if os.environ.get(...) else []` numa linha: sem a
    chave, devolvia lista vazia em silêncio logo depois de imprimir que ia
    buscar. Ficava idêntico a "procurei e não achei nada", e é possível
    passar semanas achando que o YouTube está entrando na conta.
    """
    if not os.environ.get("YOUTUBE_API_KEY", "").strip():
        print("      ⚠️  PULADO: não encontrei YOUTUBE_API_KEY.")
        print(f"         Chaves no ambiente: {', '.join(_chaves_carregadas()) or '(nenhuma)'}")
        for linha in _raio_x_do_env():
            print(f"         {linha}")
        return []
    try:
        return descobrir_virais(config)
    except Exception as e:
        # A coleta do TikTok já veio; perder o YouTube não justifica jogar fora
        # a rodada inteira. Mas o motivo tem de aparecer.
        print(f"      ⚠️  O YouTube não entrou nesta rodada: {e}")
        return []


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
        conferir_anthropic(RAIZ)  # antes da coleta: ela leva minutos

    config = yaml.safe_load(caminho_config.read_text(encoding="utf-8"))
    saida = RAIZ / "saida" / args.nicho / date.today().isoformat()
    saida.mkdir(parents=True, exist_ok=True)

    print(f"🔎 Coletando sinais de tendência do nicho '{config['nome']}'...")
    sinais = {}
    tem_apify = bool(os.environ.get("APIFY_API_TOKEN"))

    if args.coleta in ("auto", "local"):
        print("   TikTok — coleta local pelo seu navegador (grátis, sem cota)...")
        por_termo: dict[str, int] = {}
        sinais["tiktok_virais"] = virais_tiktok_local(config, estatisticas=por_termo)
        print(f"   → {len(sinais['tiktok_virais'])} vídeos coletados localmente")
        sugeridos = relatorio(sinais["tiktok_virais"], config)
        rodadas = registrar_termos(RAIZ, args.nicho, por_termo,
                                   sinais["tiktok_virais"], sugeridos)
        print(f"   📁 Desempenho dos termos registrado ({rodadas} coleta(s) na memória)")

    poucos = len(sinais.get("tiktok_virais", [])) < 5
    if args.coleta == "apify" or (args.coleta == "auto" and poucos and tem_apify):
        if poucos and args.coleta == "auto":
            print("   Coleta local trouxe pouca coisa — usando o Apify como reserva...")
        sinais["tiktok_virais"] = virais_tiktok(config) or sinais.get("tiktok_virais", [])
        print("   Instagram — top posts das hashtags do nicho (via Apify)...")
        sinais["instagram_virais"] = virais_instagram(config)

    print("   YouTube Shorts — vídeos virais do nicho (API oficial, grátis)...")
    sinais["youtube_virais"] = _virais_youtube(config)

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
    roteiros = gerar_roteiros(config, sinais, historico, raiz=RAIZ, nicho=args.nicho)
    (saida / "roteiros.json").write_text(
        json.dumps(roteiros, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"   {len(roteiros['ideias'])} roteiros -> {saida / 'roteiros.json'}")

    print("🗓️  Montando a agenda semanal...")
    agenda = montar_agenda(config, roteiros, sinais)
    (saida / "agenda.md").write_text(agenda, encoding="utf-8")
    print(f"✅ Agenda pronta: {saida / 'agenda.md'}")

    if args.publicar_site:
        from src.publicar.site import publicar_agenda, semana_seguinte
        semana, gerado_em = semana_seguinte(), date.today().isoformat()
        destino = publicar_agenda(config, roteiros, sinais, RAIZ, nicho=args.nicho,
                                  semana=semana, gerado_em=gerado_em)
        # persiste a geração para permitir re-render (mudança de design)
        # sem custo de IA — ver src/publicar/rerender.py
        dados_dir = RAIZ / "dados"
        dados_dir.mkdir(exist_ok=True)
        (dados_dir / f"{args.nicho}.json").write_text(
            json.dumps({"semana": semana, "gerado_em": gerado_em,
                        "roteiros": roteiros, "sinais": sinais},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        total_hist = registrar_historico(RAIZ, args.nicho, roteiros)
        print(f"🧠 Histórico atualizado ({total_hist} ideias acumuladas)")
        print(f"🌐 Site atualizado: {destino}")


if __name__ == "__main__":
    main()
