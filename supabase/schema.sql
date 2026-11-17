-- Timely Ride Log database (Supabase / Postgres). Run once in Supabase: SQL Editor -> New query -> paste -> Run.
-- Safe to run again (it only creates what is missing and replaces the functions).
--
-- Who can do what:
--   * Browsers (anon / authenticated roles) can do NOTHING: row level security is on with no policies, and all
--     table and function grants are revoked from them. Nobody can read anyone's rows from a browser.
--   * The Vercel function /api/ride-log uses the service key and calls ride_log_submit(), which only inserts a ride,
--     or updates a ride whose device_id matches the caller's device. Events are insert-once by id (retries are no-ops),
--     except the "undone" flag, which the same device can set.
-- Stored: a first name (optional), stations and times. No email, phone, location or IP address (rate limits use a hash).

create table if not exists public.rides (
  id              uuid primary key,
  device_id       uuid not null,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  nick            text check (char_length(nick) <= 24),
  date            date not null,
  weekday         text,
  service         text check (service in ('weekday','monday','sunday','holiday')),
  line            text not null check (line in ('G','P','Y')),
  dir             smallint not null check (dir in (0,1)),
  towards         text,
  option_index    int,
  pattern_index   int,
  from_station    int,
  from_name       text,
  matched_profile int,
  matched_start   int,
  start_ts        bigint,
  end_ts          bigint,
  done            boolean not null default false
);
create index if not exists rides_device_idx on public.rides (device_id);
create index if not exists rides_date_idx on public.rides (date);

create table if not exists public.ride_events (
  id            uuid primary key,
  ride_id       uuid not null references public.rides(id) on delete cascade,
  kind          text not null check (kind in ('board','stop','open','close','move','skip','alight')),
  station_index int not null,
  sec_ist       numeric(8,1) not null check (sec_ist >= 0 and sec_ist <= 86400),
  client_ts     bigint not null,
  undone        boolean not null default false,
  received_at   timestamptz not null default now()
);
create index if not exists ride_events_ride_idx on public.ride_events (ride_id);

create table if not exists public.ride_log_rate (
  key          text primary key,
  window_start timestamptz not null,
  hits         int not null
);

alter table public.rides         enable row level security;
alter table public.ride_events   enable row level security;
alter table public.ride_log_rate enable row level security;
revoke all on public.rides, public.ride_events, public.ride_log_rate from anon, authenticated;

-- counts one request against a key; true while under the limit for the current window
create or replace function public.ride_log_rate_hit(p_key text, p_limit int, p_window_s int)
returns boolean language plpgsql security definer set search_path = public as $$
declare n int;
begin
  insert into ride_log_rate as r (key, window_start, hits) values (p_key, now(), 1)
  on conflict (key) do update set
    hits         = case when r.window_start < now() - make_interval(secs => p_window_s) then 1 else r.hits + 1 end,
    window_start = case when r.window_start < now() - make_interval(secs => p_window_s) then now() else r.window_start end
  returning hits into n;
  return n <= p_limit;
end $$;

-- upsert one ride (only by its own device) and insert its events once; returns the event ids now stored for this ride
create or replace function public.ride_log_submit(p_device uuid, p_ride jsonb, p_events jsonb)
returns jsonb language plpgsql security definer set search_path = public as $$
declare rid uuid := (p_ride->>'id')::uuid; ok_ids jsonb;
begin
  insert into rides as r (id, device_id, nick, date, weekday, service, line, dir, towards, option_index, pattern_index,
                          from_station, from_name, matched_profile, matched_start, start_ts, end_ts, done)
  values (rid, p_device, p_ride->>'nick', (p_ride->>'date')::date, p_ride->>'weekday', p_ride->>'service', p_ride->>'line',
          (p_ride->>'dir')::smallint, p_ride->>'towards', (p_ride->>'option_index')::int, (p_ride->>'pattern_index')::int,
          (p_ride->>'from_station')::int, p_ride->>'from_name', (p_ride->>'matched_profile')::int, (p_ride->>'matched_start')::numeric::int,
          (p_ride->>'start_ts')::bigint, (p_ride->>'end_ts')::bigint, coalesce((p_ride->>'done')::boolean, false))
  on conflict (id) do update set
    nick = excluded.nick, matched_profile = excluded.matched_profile, matched_start = excluded.matched_start,
    end_ts = excluded.end_ts, done = r.done or excluded.done, updated_at = now()
  where r.device_id = excluded.device_id;

  if not exists (select 1 from rides where id = rid and device_id = p_device) then
    return jsonb_build_object('ok', false, 'error', 'not_owner');
  end if;

  insert into ride_events as x (id, ride_id, kind, station_index, sec_ist, client_ts, undone)
  select (e->>'id')::uuid, rid, e->>'kind', (e->>'station_index')::int, (e->>'sec_ist')::numeric, (e->>'client_ts')::bigint,
         coalesce((e->>'undone')::boolean, false)
  from jsonb_array_elements(coalesce(p_events, '[]'::jsonb)) e
  on conflict (id) do update set undone = excluded.undone
  where x.ride_id = excluded.ride_id;

  select coalesce(jsonb_agg(e->>'id'), '[]'::jsonb) into ok_ids
  from jsonb_array_elements(coalesce(p_events, '[]'::jsonb)) e
  where exists (select 1 from ride_events y where y.id = (e->>'id')::uuid and y.ride_id = rid);

  return jsonb_build_object('ok', true, 'events', ok_ids);
end $$;

-- daily keep-alive from Vercel Cron: clears old rate rows, returns the number of rides
create or replace function public.ride_log_ping()
returns bigint language plpgsql security definer set search_path = public as $$
begin
  delete from ride_log_rate where window_start < now() - interval '1 day';
  return (select count(*) from rides);
end $$;

revoke all on function public.ride_log_rate_hit(text, int, int) from public, anon, authenticated;
revoke all on function public.ride_log_submit(uuid, jsonb, jsonb) from public, anon, authenticated;
revoke all on function public.ride_log_ping() from public, anon, authenticated;
grant execute on function public.ride_log_rate_hit(text, int, int) to service_role;
grant execute on function public.ride_log_submit(uuid, jsonb, jsonb) to service_role;
grant execute on function public.ride_log_ping() to service_role;
grant select on public.rides, public.ride_events to service_role;   -- for scripts/export_rides.py
