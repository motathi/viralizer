"""Publica a agenda gerada como página do site (web/index.html).

Renderiza os roteiros da semana no mesmo visual da vitrine, para que o
deploy da Vercel (que serve a pasta web/) sempre mostre a agenda atual.
"""

from datetime import date, timedelta
from html import escape
from pathlib import Path

from src.agenda.montador import SLOTS_SEMANA

ESTILO = """
  :root {
    --fundo: #faf8f6; --tinta: #2b2430; --suave: #6f6678;
    --acento: #b0578d; --acento-claro: #f3e2ed; --card: #ffffff;
    --borda: #e9e2e5; --ok: #2e7d5b;
  }
  * { box-sizing: border-box; margin: 0; }
  body { font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
         background: var(--fundo); color: var(--tinta); line-height: 1.6; }
  .container { max-width: 860px; margin: 0 auto; padding: 0 20px; }
  header { padding: 48px 0 28px; text-align: center; }
  .selo { display: inline-block; background: var(--acento-claro); color: var(--acento);
          font-size: .8rem; font-weight: 600; padding: 4px 14px; border-radius: 999px;
          letter-spacing: .04em; text-transform: uppercase; margin-bottom: 18px; }
  h1 { font-size: clamp(1.6rem, 5vw, 2.3rem); line-height: 1.2; }
  h1 span { color: var(--acento); }
  .sub { color: var(--suave); max-width: 560px; margin: 14px auto 0; }
  section.agenda { padding: 10px 0 60px; }
  .aviso { background: var(--acento-claro); border-radius: 10px; padding: 10px 16px;
           font-size: .85rem; margin: 12px 0 26px; }
  .cartao { background: var(--card); border: 1px solid var(--borda); border-radius: 16px;
            padding: 26px 26px 20px; margin-bottom: 22px; }
  .topo { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 10px; }
  .chip { font-size: .75rem; font-weight: 600; padding: 3px 11px; border-radius: 999px;
          background: var(--acento-claro); color: var(--acento); }
  .chip.dia { background: #e8f2ec; color: var(--ok); }
  .cartao h3 { font-size: 1.15rem; margin-bottom: 10px; }
  .rotulo { font-size: .78rem; font-weight: 700; text-transform: uppercase;
            letter-spacing: .05em; color: var(--acento); margin: 16px 0 4px; }
  .gancho { font-style: italic; background: var(--fundo); border-left: 3px solid var(--acento);
            padding: 10px 14px; border-radius: 0 8px 8px 0; }
  .texto { font-size: .93rem; white-space: pre-wrap; }
  ul.refs { padding-left: 20px; font-size: .93rem; }
  .linha-final { display: flex; flex-wrap: wrap; gap: 16px; margin-top: 16px;
                 font-size: .88rem; color: var(--suave); }
  footer { border-top: 1px solid var(--borda); padding: 26px 0 40px; text-align: center;
           color: var(--suave); font-size: .85rem; }
"""


def _cartao(ideia: dict, posicao: int) -> str:
    dia, hora = SLOTS_SEMANA[posicao % len(SLOTS_SEMANA)]
    origem = ideia.get("plataforma_origem_da_tendencia", "")
    refs = "".join(f"<li>{escape(r)}</li>" for r in ideia.get("embasamento_cientifico", []))
    hashtags = escape(" ".join(ideia.get("hashtags", [])))
    return f"""
  <article class="cartao">
    <div class="topo">
      <span class="chip dia">{escape(dia)} · {escape(hora)}</span>
      <span class="chip">{escape(ideia.get('pilar', ''))}</span>
      <span class="chip">~{ideia.get('duracao_estimada_seg', '?')}s</span>
      {f'<span class="chip">Tendência: {escape(origem)}</span>' if origem else ''}
    </div>
    <h3>{escape(ideia.get('titulo', ''))}</h3>
    <div class="rotulo">Gancho — 3 primeiros segundos</div>
    <p class="gancho">{escape(ideia.get('gancho_3s', ''))}</p>
    <div class="rotulo">Roteiro</div>
    <p class="texto">{escape(ideia.get('roteiro', ''))}</p>
    <div class="rotulo">Por que deve performar</div>
    <p class="texto">{escape(ideia.get('embasamento_viral', ''))}</p>
    <div class="rotulo">Embasamento científico</div>
    <ul class="refs">{refs}</ul>
    <div class="linha-final">
      <span>⚖️ {escape(ideia.get('conformidade_cfm', 'Conformidade CFM verificada'))}</span>
      <span>📣 CTA: {escape(ideia.get('cta', ''))}</span>
      <span>{hashtags}</span>
    </div>
  </article>"""


def publicar_site(config: dict, roteiros: dict, sinais: dict, destino: Path) -> None:
    """Escreve a agenda da semana como web/index.html."""
    ideias = roteiros["ideias"]
    total_sinais = sum(len(v) for v in sinais.values())
    inicio = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 or 7)
    cartoes = "".join(_cartao(ideia, i) for i, ideia in enumerate(ideias))

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Radar de Conteúdo Viral — {escape(config['nome'])}</title>
<style>{ESTILO}</style>
</head>
<body>
<header class="container">
  <div class="selo">Radar de Conteúdo Viral</div>
  <h1>Agenda da semana — <span>{escape(config['nome'])}</span></h1>
  <p class="sub">Semana de {inicio.strftime('%d/%m/%Y')} · {len(ideias)} conteúdos ·
  gerada automaticamente a partir de {total_sinais} sinais de tendência
  (TikTok, Instagram e YouTube), atualizada em {date.today().strftime('%d/%m/%Y')}.</p>
</header>
<section class="agenda container">
  <div class="aviso">⚕️ Todo conteúdo é um rascunho embasado: a palavra final sobre
  qualquer afirmação médica é sempre da profissional.</div>
  {cartoes}
</section>
<footer>
  <div class="container">
    <p><strong>Radar de Conteúdo Viral</strong> — pesquisa de tendências, roteiros embasados e agenda semanal.</p>
  </div>
</footer>
</body>
</html>
"""
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
