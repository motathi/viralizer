-- Estado compartilhado do Radar de Conteúdo Viral
--
-- Rode este arquivo uma vez, no SQL Editor do seu projeto Supabase
-- (menu lateral → SQL Editor → New query → colar → Run).
--
-- Duas tabelas:
--   radar_estado — o que cada ideia é hoje: na lista, feita, descartada,
--                  qual gancho e qual formato foram escolhidos.
--   radar_ideias — as ideias criadas no estúdio.
--
-- Segurança: RLS ligado e SEM nenhuma policy. Isso faz a chave pública
-- (sb_publishable_…) não conseguir ler nem escrever nada. Quem acessa é o
-- servidor do site, com a chave secreta (sb_secret_…), que passa por cima
-- da RLS. É o mesmo desenho da chave da Anthropic: segredo só no servidor.

create table if not exists public.radar_estado (
  nicho          text        not null,
  ideia_id       text        not null,
  lista          boolean     not null default false,
  feita          boolean     not null default false,
  descartada     boolean     not null default false,
  gancho         smallint    not null default 0,
  formato        text        not null default 'reels',
  atualizado_em  timestamptz not null default now(),
  primary key (nicho, ideia_id)
);

create table if not exists public.radar_ideias (
  nicho          text        not null,
  id             text        not null,
  ideia          text        not null default '',
  formato        text        not null default 'video',
  estilo         text        not null default '',
  tom            text        not null default '',
  tamanho        text        not null default '',
  roteiro        jsonb       not null default '{}'::jsonb,
  criado_em      timestamptz not null default now(),
  atualizado_em  timestamptz not null default now(),
  primary key (nicho, id)
);

create index if not exists radar_estado_nicho_idx on public.radar_estado (nicho);
create index if not exists radar_ideias_nicho_idx on public.radar_ideias (nicho, atualizado_em desc);

alter table public.radar_estado enable row level security;
alter table public.radar_ideias enable row level security;

-- ── escritas ────────────────────────────────────────────────────────────
-- Feitas por função, e não por upsert do PostgREST, para o "insere ou
-- atualiza" ficar explícito aqui, num lugar só.

create or replace function public.radar_definir_estado(
  p_nicho text, p_ideia_id text, p_estado jsonb
) returns void language sql as $$
  insert into public.radar_estado
    (nicho, ideia_id, lista, feita, descartada, gancho, formato, atualizado_em)
  values (
    p_nicho, p_ideia_id,
    coalesce((p_estado->>'lista')::boolean, false),
    coalesce((p_estado->>'feito')::boolean, false),
    coalesce((p_estado->>'descartada')::boolean, false),
    coalesce((p_estado->>'gancho')::smallint, 0),
    coalesce(p_estado->>'formato', 'reels'),
    now()
  )
  on conflict (nicho, ideia_id) do update set
    lista = excluded.lista, feita = excluded.feita, descartada = excluded.descartada,
    gancho = excluded.gancho, formato = excluded.formato, atualizado_em = now();
$$;

create or replace function public.radar_salvar_ideia(
  p_nicho text, p_id text, p_dados jsonb
) returns void language sql as $$
  insert into public.radar_ideias
    (nicho, id, ideia, formato, estilo, tom, tamanho, roteiro, atualizado_em)
  values (
    p_nicho, p_id,
    coalesce(p_dados->>'ideia', ''),
    coalesce(p_dados->>'formato', 'video'),
    coalesce(p_dados->>'estilo', ''),
    coalesce(p_dados->>'tom', ''),
    coalesce(p_dados->>'tamanho', ''),
    coalesce(p_dados->'roteiro', '{}'::jsonb),
    now()
  )
  on conflict (nicho, id) do update set
    ideia = excluded.ideia, formato = excluded.formato, estilo = excluded.estilo,
    tom = excluded.tom, tamanho = excluded.tamanho, roteiro = excluded.roteiro,
    atualizado_em = now();
$$;

-- Apagar é apagar mesmo: some para todo mundo, em qualquer aparelho.
create or replace function public.radar_apagar_ideia(
  p_nicho text, p_id text
) returns void language sql as $$
  delete from public.radar_ideias where nicho = p_nicho and id = p_id;
  delete from public.radar_estado where nicho = p_nicho and ideia_id = p_id;
$$;

-- Só o servidor (chave secreta) chama estas funções.
revoke execute on function public.radar_definir_estado(text, text, jsonb) from anon, authenticated;
revoke execute on function public.radar_salvar_ideia(text, text, jsonb)   from anon, authenticated;
revoke execute on function public.radar_apagar_ideia(text, text)          from anon, authenticated;

-- Mantém o projeto gratuito acordado: o GitHub Actions chama isto todo dia.
-- Projeto do plano grátis que passa 7 dias sem consultas é pausado.
create or replace function public.radar_ping() returns timestamptz
  language sql as $$ select now(); $$;
revoke execute on function public.radar_ping() from anon, authenticated;
