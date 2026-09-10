/**
 * Estado compartilhado: o que uma pessoa marca ou apaga vale para todas.
 *
 * Antes, cada navegador guardava as próprias escolhas, então apagar uma
 * ideia num aparelho a deixava viva nos outros. Agora o estado mora no
 * Supabase, e esta função é a única porta: a chave secreta fica aqui no
 * servidor (SUPABASE_SECRET_KEY), nunca no navegador. As tabelas estão
 * com RLS ligado e sem policy, então a chave pública não abre nada.
 *
 * Variáveis de ambiente (Vercel → Settings → Environment Variables):
 *   SUPABASE_URL         https://<ref>.supabase.co
 *   SUPABASE_SECRET_KEY  sb_secret_... (Settings → API Keys)
 *
 * Sem elas a função responde {configurado:false} e o site volta a guardar
 * tudo no navegador, como antes — nada quebra, só não sincroniza.
 *
 * Rotas:
 *   GET  /api/estado?nicho=X   -> {configurado, estado, ideias}
 *   POST /api/estado           -> {nicho, acao:"estado"|"ideia"|"apagar", id, dados}
 *
 * O painel local atende as mesmas rotas com as chaves do .env
 * (src/painel/servidor.py), para o site funcionar igual nos dois lugares.
 */

const MAX_ID = 200;
const MAX_CORPO = 200000; // caracteres do JSON de uma ideia

const url = () => (process.env.SUPABASE_URL || '').trim().replace(/\/+$/, '');
const chave = () => (process.env.SUPABASE_SECRET_KEY || '').trim();
const configurado = () => !!(url() && chave());

function json(dados, status = 200) {
  return new Response(JSON.stringify(dados), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  });
}

/**
 * As chaves novas (sb_secret_…) NÃO são JWT e são recusadas se forem
 * enviadas em Authorization; vão só em apikey. As antigas (service_role,
 * um JWT que começa com eyJ) continuam aceitas nos dois lugares.
 */
function cabecalhos() {
  const k = chave();
  const h = { apikey: k, 'content-type': 'application/json' };
  if (k.startsWith('ey')) h.authorization = `Bearer ${k}`;
  return h;
}

async function supabase(caminho, opcoes = {}) {
  const r = await fetch(`${url()}/rest/v1/${caminho}`, { ...opcoes, headers: cabecalhos() });
  if (!r.ok) {
    let detalhe = '';
    try { detalhe = (await r.json()).message || ''; } catch (_) {}
    const e = new Error(detalhe || `Supabase respondeu ${r.status}`);
    e.status = r.status;
    throw e;
  }
  return r.status === 204 ? null : r.json();
}

const rpc = (nome, args) =>
  supabase(`rpc/${nome}`, { method: 'POST', body: JSON.stringify(args) });

function recadoDoErro(e) {
  const s = e?.status;
  if (s === 401 || s === 403) {
    return 'O Supabase recusou a chave do site. Confira SUPABASE_SECRET_KEY na Vercel — tem de ser a chave secreta, não a publicável.';
  }
  if (s === 404) {
    return 'As tabelas do Radar não existem neste projeto Supabase. Rode supabase/schema.sql no SQL Editor.';
  }
  if (s === 540) {
    return 'O projeto do Supabase está pausado (plano grátis pausa após 7 dias parado). Clique em Resume no painel do Supabase.';
  }
  return `Não consegui falar com o banco: ${String(e?.message || e).slice(0, 200)}`;
}

const limpo = (v, max) => String(v ?? '').slice(0, max);

export async function GET(request) {
  if (!configurado()) return json({ configurado: false, estado: {}, ideias: [] });
  const nicho = limpo(new URL(request.url).searchParams.get('nicho') || 'padrao', MAX_ID);
  try {
    const [linhas, ideias] = await Promise.all([
      supabase(`radar_estado?nicho=eq.${encodeURIComponent(nicho)}&select=*`),
      supabase(`radar_ideias?nicho=eq.${encodeURIComponent(nicho)}&select=*&order=atualizado_em.desc`),
    ]);
    const estado = {};
    for (const l of linhas || []) {
      estado[l.ideia_id] = {lista: l.lista, feito: l.feita, descartada: l.descartada,
                            gancho: l.gancho, formato: l.formato};
    }
    return json({
      configurado: true, estado,
      ideias: (ideias || []).map(i => ({
        id: i.id, ideia: i.ideia, formato: i.formato, estilo: i.estilo, tom: i.tom,
        tamanho: i.tamanho, roteiro: i.roteiro, criado_em: i.criado_em,
        atualizado_em: i.atualizado_em, origem: 'banco',
      })),
    });
  } catch (e) {
    return json({ configurado: true, erro: 'banco', recado: recadoDoErro(e), estado: {}, ideias: [] }, 200);
  }
}

export async function POST(request) {
  if (!configurado()) return json({ ok: false, configurado: false });
  let pedido;
  try { pedido = await request.json(); }
  catch (_) { return json({ ok: false, recado: 'Pedido inválido.' }, 400); }

  const nicho = limpo(pedido.nicho || 'padrao', MAX_ID);
  const id = limpo(pedido.id, MAX_ID);
  if (!id) return json({ ok: false, recado: 'Pedido sem id.' }, 400);
  const corpo = JSON.stringify(pedido.dados || {});
  if (corpo.length > MAX_CORPO) return json({ ok: false, recado: 'Pedido grande demais.' }, 413);

  try {
    if (pedido.acao === 'estado') {
      await rpc('radar_definir_estado', { p_nicho: nicho, p_ideia_id: id, p_estado: pedido.dados || {} });
    } else if (pedido.acao === 'ideia') {
      await rpc('radar_salvar_ideia', { p_nicho: nicho, p_id: id, p_dados: pedido.dados || {} });
    } else if (pedido.acao === 'apagar') {
      await rpc('radar_apagar_ideia', { p_nicho: nicho, p_id: id });
    } else {
      return json({ ok: false, recado: 'Ação desconhecida.' }, 400);
    }
    return json({ ok: true });
  } catch (e) {
    return json({ ok: false, recado: recadoDoErro(e) }, 200);
  }
}
