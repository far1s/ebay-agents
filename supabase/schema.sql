-- EtsyAgents Database Schema
-- Run this in your Supabase SQL editor

-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- ── Agent Runs ────────────────────────────────────────────────────────────────
create table if not exists agent_runs (
  id            uuid primary key default uuid_generate_v4(),
  run_id        text unique not null,
  started_at    timestamptz not null default now(),
  completed_at  timestamptz,
  status        text not null default 'running'
                  check (status in ('running', 'completed', 'failed', 'cancelled')),
  boss_report   jsonb,
  created_at    timestamptz not null default now()
);

create index if not exists agent_runs_status_idx on agent_runs(status);
create index if not exists agent_runs_started_at_idx on agent_runs(started_at desc);

-- ── Agent Performance ─────────────────────────────────────────────────────────
create table if not exists agent_performance (
  id          uuid primary key default uuid_generate_v4(),
  run_id      text not null references agent_runs(run_id) on delete cascade,
  agent_name  text not null,
  score       int not null check (score between 1 and 10),
  notes       text,
  timestamp   timestamptz not null default now()
);

create index if not exists agent_performance_run_id_idx on agent_performance(run_id);
create index if not exists agent_performance_agent_name_idx on agent_performance(agent_name);

-- ── Market Research ───────────────────────────────────────────────────────────
create table if not exists market_research (
  id                uuid primary key default uuid_generate_v4(),
  run_id            text not null references agent_runs(run_id) on delete cascade,
  product_type      text not null,
  keywords          text[] not null default '{}',
  avg_price         numeric(10,2),
  sales_volume      int,
  opportunity_score numeric(4,2),
  raw_data          jsonb,
  created_at        timestamptz not null default now()
);

create index if not exists market_research_run_id_idx on market_research(run_id);
create index if not exists market_research_opportunity_idx on market_research(opportunity_score desc);

-- ── Generated Products ────────────────────────────────────────────────────────
create table if not exists generated_products (
  id            uuid primary key default uuid_generate_v4(),
  run_id        text not null references agent_runs(run_id) on delete cascade,
  product_type  text not null,
  file_path     text not null,
  preview_path  text,
  design_score  int check (design_score between 1 and 10),
  metadata      jsonb,
  created_at    timestamptz not null default now()
);

create index if not exists generated_products_run_id_idx on generated_products(run_id);

-- ── Approval Log ──────────────────────────────────────────────────────────────
create table if not exists approval_log (
  id                  uuid primary key default uuid_generate_v4(),
  run_id              text not null references agent_runs(run_id) on delete cascade,
  product_id          uuid references generated_products(id),
  suggested_price     numeric(10,2) not null,
  final_price         numeric(10,2),
  status              text not null default 'pending'
                        check (status in ('pending', 'approved', 'rejected', 'timeout', 'custom_price')),
  telegram_message_id bigint,
  decided_at          timestamptz,
  created_at          timestamptz not null default now()
);

create index if not exists approval_log_run_id_idx on approval_log(run_id);
create index if not exists approval_log_status_idx on approval_log(status);

-- ── Etsy Listings ─────────────────────────────────────────────────────────────
create table if not exists listings (
  id                uuid primary key default uuid_generate_v4(),
  run_id            text not null references agent_runs(run_id) on delete cascade,
  product_id        uuid references generated_products(id),
  etsy_listing_id   text unique,
  etsy_url          text,
  title             text not null,
  price             numeric(10,2) not null,
  status            text not null default 'active'
                      check (status in ('active', 'sold', 'ended', 'error')),
  listed_at         timestamptz not null default now()
);

create index if not exists listings_status_idx on listings(status);
create index if not exists listings_listed_at_idx on listings(listed_at desc);

-- ── Agent Logs ────────────────────────────────────────────────────────────────
create table if not exists agent_logs (
  id          uuid primary key default uuid_generate_v4(),
  run_id      text,
  agent_name  text not null,
  level       text not null default 'info'
                check (level in ('debug', 'info', 'warning', 'error')),
  message     text not null,
  metadata    jsonb,
  timestamp   timestamptz not null default now()
);

create index if not exists agent_logs_run_id_idx on agent_logs(run_id);
create index if not exists agent_logs_agent_name_idx on agent_logs(agent_name);
create index if not exists agent_logs_level_idx on agent_logs(level);
create index if not exists agent_logs_timestamp_idx on agent_logs(timestamp desc);

-- ── Row Level Security ────────────────────────────────────────────────────────
-- Service role key bypasses RLS; anon key (dashboard) gets read-only access

alter table agent_runs        enable row level security;
alter table agent_performance enable row level security;
alter table market_research   enable row level security;
alter table generated_products enable row level security;
alter table approval_log      enable row level security;
alter table listings          enable row level security;
alter table agent_logs        enable row level security;

-- Read-only policy for all tables (anon / authenticated)
create policy "Allow read" on agent_runs        for select using (true);
create policy "Allow read" on agent_performance for select using (true);
create policy "Allow read" on market_research   for select using (true);
create policy "Allow read" on generated_products for select using (true);
create policy "Allow read" on approval_log      for select using (true);
create policy "Allow read" on listings          for select using (true);
create policy "Allow read" on agent_logs        for select using (true);
