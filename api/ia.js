/**
 * Proxy da IA: a chave fica aqui no servidor, não no navegador de cada pessoa.
 *
 * O estúdio do site chama POST /api/ia; esta função repassa para a Anthropic
 * usando a chave guardada na variável de ambiente ANTHROPIC_API_KEY (painel da
 * Vercel → Settings → Environment Variables). A chave nunca é enviada ao
 * navegador e não fica no repositório.
 *
 * GET /api/ia diz se há chave configurada e se o acesso pede senha — é o que a
 * página de Ferramentas mostra.
 *
 * O painel local atende a mesma rota com a chave do .env (src/painel/servidor.py),
 * então as páginas funcionam igual nos dois lugares.
 *
 * Como o endereço é público, aqui ficam as travas: só os modelos que o site usa,
 * teto de tokens, teto de tamanho, limite por IP e, se RADAR_SENHA estiver
 * definida, uma senha de acesso.
 */

import Anthropic from '@anthropic-ai/sdk';

// Espelham os modelos de src/roteiros/gerador.py — a lista fecha a porta para
// quem quiser usar este endereço como um Claude de uso geral.
const MODELOS = new Set(['claude-opus-5', 'claude-haiku-4-5']);
const MAX_TOKENS = 20000;
const MAX_SYSTEM = 60000; // caracteres
const MAX_MENSAGENS = 30;
const MAX_CONTEUDO = 250000; // caracteres somados das mensagens

// Limite por IP. Em serverless a memória é por instância e some quando ela
// hiberna, então isto atrasa o abuso, não o impede: a proteção que vale é o
// limite de gasto no console da Anthropic, e a senha abaixo.
const JANELA_MS = 60 * 60 * 1000;
const LIMITE_POR_IP = 40;
const acessos = new Map();

function dentroDoLimite(ip) {
  const agora = Date.now();
  const recentes = (acessos.get(ip) || []).filter((t) => agora - t < JANELA_MS);
  if (recentes.length >= LIMITE_POR_IP) {
    acessos.set(ip, recentes);
    return false;
  }
  recentes.push(agora);
  acessos.set(ip, recentes);
  if (acessos.size > 5000) acessos.clear(); // não deixar a memória crescer sem fim
  return true;
}

const chave = () => (process.env.ANTHROPIC_API_KEY || '').trim();
const senhaExigida = () => (process.env.RADAR_SENHA || '').trim();

function json(dados, status = 200) {
  return new Response(JSON.stringify(dados), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  });
}

function ipDe(request) {
  const encaminhado = request.headers.get('x-forwarded-for') || '';
  return encaminhado.split(',')[0].trim() || request.headers.get('x-real-ip') || 'desconhecido';
}

/** Erro técnico da API traduzido para quem vai ler na tela. */
function recadoDoErro(e) {
  const status = e?.status;
  const texto = String(e?.message || e || '').toLowerCase();
  if (status === 401 || texto.includes('authentication') || texto.includes('x-api-key')) {
    return 'A chave da Anthropic configurada no site não foi aceita. Quem administra precisa conferi-la na Vercel.';
  }
  if (texto.includes('credit balance')) {
    return 'Os créditos da Anthropic acabaram. Recarregue em console.anthropic.com (Plans & Billing).';
  }
  if (status === 429) return 'A Anthropic pediu para esperar um pouco (limite de uso). Tente de novo em um minuto.';
  if (status === 529 || status === 503) return 'A Anthropic está sobrecarregada agora. Tente de novo em instantes.';
  if (status === 404) return 'O modelo configurado não está disponível para a chave do site.';
  const cru = String(e?.message || e || '').slice(0, 200);
  return cru ? `A IA respondeu com erro: ${cru}` : 'A IA respondeu com erro.';
}

/**
 * Diagnóstico: quais variáveis de ambiente a função enxerga.
 *
 * Devolve só os NOMES, nunca os valores, e só dos prefixos que este
 * projeto usa — nomes que já estão documentados no README. Serve para
 * separar duas causas que dão o mesmo sintoma: a variável foi criada com
 * outro nome, ou foi criada em outro projeto/ambiente da Vercel.
 */
function variaveisVistas() {
  return Object.keys(process.env)
    .filter((n) => /^(SUPABASE|ANTHROPIC|RADAR|POSTGRES)_/.test(n))
    .sort();
}

export function GET() {
  return json({
    variaveis: variaveisVistas(),
    configurada: !!chave(),
    senha: !!senhaExigida(),
    painel: false,
    modelos: [...MODELOS],
    max_tokens: MAX_TOKENS,
  });
}

export async function POST(request) {
  if (!chave()) {
    return json(
      {
        erro: 'sem_chave',
        recado:
          'O site ainda não tem uma chave da Anthropic. Quem administra precisa criar a variável ' +
          'de ambiente ANTHROPIC_API_KEY na Vercel (Settings → Environment Variables) e publicar de novo.',
      },
      503,
    );
  }

  let pedido;
  try {
    pedido = await request.json();
  } catch (_) {
    return json({ erro: 'pedido_invalido', recado: 'Pedido inválido.' }, 400);
  }

  const exigida = senhaExigida();
  if (exigida && String(pedido.senha || '') !== exigida) {
    return json(
      {
        erro: 'senha',
        recado: 'Este site pede uma senha de acesso à IA. Guarde a sua em Ferramentas → Estado da IA.',
      },
      401,
    );
  }

  if (!dentroDoLimite(ipDe(request))) {
    return json(
      {
        erro: 'limite',
        recado: `Você já fez ${LIMITE_POR_IP} pedidos à IA nesta última hora. Espere um pouco e tente de novo.`,
      },
      429,
    );
  }

  const modelo = String(pedido.modelo || '');
  if (!MODELOS.has(modelo)) {
    return json({ erro: 'modelo', recado: 'Modelo não permitido neste site.' }, 400);
  }

  const system = String(pedido.system || '');
  const mensagens = Array.isArray(pedido.messages) ? pedido.messages : [];
  const tamanho = mensagens.reduce((n, m) => n + String(m?.content || '').length, 0);
  if (system.length > MAX_SYSTEM || mensagens.length > MAX_MENSAGENS || tamanho > MAX_CONTEUDO) {
    return json({ erro: 'tamanho', recado: 'O pedido ficou grande demais para o site.' }, 413);
  }
  if (!mensagens.length) {
    return json({ erro: 'pedido_invalido', recado: 'Pedido sem mensagens.' }, 400);
  }

  const corpo = {
    model: modelo,
    max_tokens: Math.min(Number(pedido.max_tokens) || 16000, MAX_TOKENS),
    system,
    messages: mensagens.map((m) => ({
      role: m.role === 'assistant' ? 'assistant' : 'user',
      content: String(m.content || ''),
    })),
  };
  // Só Opus 5 aceita pensamento adaptativo; Haiku (o teste da chave) vai sem.
  if (pedido.thinking && modelo === 'claude-opus-5') corpo.thinking = { type: 'adaptive' };

  const cliente = new Anthropic({ apiKey: chave() });
  const codificador = new TextEncoder();
  const fluxo = new ReadableStream({
    async start(controlador) {
      const enviar = (evento) =>
        controlador.enqueue(codificador.encode(`data: ${JSON.stringify(evento)}\n\n`));
      try {
        const stream = cliente.messages.stream(corpo);
        for await (const evento of stream) {
          if (evento.type === 'content_block_delta' && evento.delta?.type === 'text_delta') {
            enviar({ type: 'content_block_delta', delta: { type: 'text_delta', text: evento.delta.text } });
          } else if (evento.type === 'message_delta' && evento.delta?.stop_reason) {
            enviar({ type: 'message_delta', delta: { stop_reason: evento.delta.stop_reason } });
          }
        }
      } catch (e) {
        enviar({ type: 'error', error: { message: recadoDoErro(e) } });
      } finally {
        controlador.close();
      }
    },
  });

  return new Response(fluxo, {
    headers: {
      'content-type': 'text/event-stream; charset=utf-8',
      'cache-control': 'no-store',
      'x-accel-buffering': 'no',
    },
  });
}
