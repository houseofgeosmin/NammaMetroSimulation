/* Timely Ride Log upload API (logic). Used by api/ride-log.js on Vercel and by tests/test_api_core.mjs locally.
   The browser never talks to the database: this function holds the Supabase service key (Vercel env only) and
   calls two Postgres functions (supabase/schema.sql). Anonymous phones can only add or change their own ride.

   Environment (Vercel project settings, never in the repo):
     SUPABASE_URL                 added by the Vercel Supabase integration (NEXT_PUBLIC_SUPABASE_URL also accepted)
     SUPABASE_SERVICE_ROLE_KEY    added by the integration (or SUPABASE_SECRET_KEY, the newer sb_secret_ key)
     RIDE_LOG_CODE_SHA256         sha256 hex of "namma-ride-log:" + access code (python scripts/hash_code.py) */
import { createHash, timingSafeEqual } from 'node:crypto';

const MAX_BODY = 256 * 1024, MAX_EVENTS = 500;
const KINDS = new Set(['board', 'stop', 'open', 'close', 'move', 'skip', 'alight']);
const DAYS = new Set(['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']);
const SERVICES = new Set(['weekday', 'monday', 'sunday', 'holiday']);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
export const LIMITS = { ipPer10Min: 300, devicePer10Min: 200, badCodePerHour: 20 };

export const codeHash = code => createHash('sha256').update('namma-ride-log:' + code).digest('hex');
const sha = s => createHash('sha256').update(s).digest('hex').slice(0, 32);
const json = (status, body, headers) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json', 'cache-control': 'no-store', ...(headers || {}) } });
function safeEq(a, b) { const x = Buffer.from(String(a)), y = Buffer.from(String(b)); return x.length === y.length && timingSafeEqual(x, y); }

export function settings(env) {
  return { url: (env.SUPABASE_URL || env.NEXT_PUBLIC_SUPABASE_URL || '').replace(/\/$/, ''),
           key: env.SUPABASE_SERVICE_ROLE_KEY || env.SUPABASE_SECRET_KEY || '',
           codeHash: (env.RIDE_LOG_CODE_SHA256 || '').trim().toLowerCase() };
}
export async function rpc(cfg, fetchFn, name, args) {
  const headers = { 'content-type': 'application/json', apikey: cfg.key };
  if (!cfg.key.startsWith('sb_')) headers.authorization = 'Bearer ' + cfg.key;   // legacy JWT keys also need the bearer header
  const r = await fetchFn(cfg.url + '/rest/v1/rpc/' + name, { method: 'POST', headers, body: JSON.stringify(args) });
  if (!r.ok) throw new Error('db ' + r.status + ' ' + (await r.text()).slice(0, 300));
  return r.json();
}

/* ---- validation: keep only the fields we store; first name, stations and times ---- */
const isInt = (v, lo, hi) => Number.isInteger(v) && v >= lo && v <= hi;
const isNum = (v, lo, hi) => typeof v === 'number' && Number.isFinite(v) && v >= lo && v <= hi;
const str = (v, max) => typeof v === 'string' ? v.replace(/[\u0000-\u001f\u007f<>]/g, '').trim().slice(0, max) : null;
export function cleanRide(r) {
  if (!r || typeof r !== 'object' || !UUID.test(r.id || '')) return null;
  const out = { id: r.id.toLowerCase(), nick: str(r.nick, 24) || 'Rider', date: r.date, weekday: r.weekday, service: r.service, line: r.line, dir: r.dir,
    towards: str(r.towards, 60), option_index: r.option_index, pattern_index: r.pattern_index, from_station: r.from_station, from_name: str(r.from_name, 60),
    matched_profile: r.matched_profile ?? null, matched_start: r.matched_start ?? null, start_ts: r.start_ts, end_ts: r.end_ts ?? null, done: r.done === true };
  const ok = /^\d{4}-\d{2}-\d{2}$/.test(out.date || '') && DAYS.has(out.weekday) && SERVICES.has(out.service) && ['G', 'P', 'Y'].includes(out.line)
    && (out.dir === 0 || out.dir === 1) && out.towards && isInt(out.option_index, 0, 200) && isInt(out.pattern_index, 0, 500) && isInt(out.from_station, 0, 500)
    && (out.matched_profile === null || isInt(out.matched_profile, 0, 5000)) && (out.matched_start === null || isNum(out.matched_start, -100000, 200000))
    && isNum(out.start_ts, 1.5e12, 4e12) && (out.end_ts === null || isNum(out.end_ts, 1.5e12, 4e12));
  return ok ? out : null;
}
export function cleanEvents(list) {
  if (!Array.isArray(list) || list.length > MAX_EVENTS) return null;
  const out = [];
  for (const e of list) {
    if (!e || !UUID.test(e.id || '') || !KINDS.has(e.kind) || !isInt(e.station_index, 0, 500) || !isNum(e.sec_ist, 0, 86400) || !isNum(e.client_ts, 1.5e12, 4e12)) return null;
    out.push({ id: e.id.toLowerCase(), kind: e.kind, station_index: e.station_index, sec_ist: Math.round(e.sec_ist * 10) / 10, client_ts: Math.round(e.client_ts), undone: e.undone === true });
  }
  return out;
}

/* ---- the request ---- */
export async function handle(request, env, fetchFn = fetch) {
  if (request.method !== 'POST') return json(405, { ok: false, error: 'method' }, { allow: 'POST' });
  const cfg = settings(env);
  if (!cfg.url || !cfg.key || !/^[0-9a-f]{64}$/.test(cfg.codeHash)) return json(503, { ok: false, error: 'not-configured' });
  if (+(request.headers.get('content-length') || 0) > MAX_BODY) return json(413, { ok: false, error: 'too-big' });
  const text = await request.text();
  if (text.length > MAX_BODY) return json(413, { ok: false, error: 'too-big' });
  let b; try { b = JSON.parse(text); } catch (e) { return json(400, { ok: false, error: 'bad-json' }); }
  const ip = (request.headers.get('x-forwarded-for') || '').split(',')[0].trim() || request.headers.get('x-real-ip') || 'unknown';
  const ipKey = 'ip:' + sha(cfg.codeHash + ip);   // hashed, never the raw address
  try {
    if (!(await rpc(cfg, fetchFn, 'ride_log_rate_hit', { p_key: ipKey, p_limit: LIMITS.ipPer10Min, p_window_s: 600 })))
      return json(429, { ok: false, error: 'rate-limited' }, { 'retry-after': '60' });
    if (typeof b.code !== 'string' || !safeEq(codeHash(b.code.trim()), cfg.codeHash)) {
      const under = await rpc(cfg, fetchFn, 'ride_log_rate_hit', { p_key: 'bad' + ipKey, p_limit: LIMITS.badCodePerHour, p_window_s: 3600 });
      return under ? json(401, { ok: false, error: 'bad-code' }) : json(429, { ok: false, error: 'rate-limited' }, { 'retry-after': '600' });
    }
    if (!UUID.test(b.device_id || '')) return json(400, { ok: false, error: 'bad-device' });
    const ride = cleanRide(b.ride), events = cleanEvents(b.events || []);
    if (!ride) return json(400, { ok: false, error: 'bad-ride' });
    if (!events) return json(400, { ok: false, error: 'bad-event' });
    if (!(await rpc(cfg, fetchFn, 'ride_log_rate_hit', { p_key: 'dev:' + sha(b.device_id), p_limit: LIMITS.devicePer10Min, p_window_s: 600 })))
      return json(429, { ok: false, error: 'rate-limited' }, { 'retry-after': '60' });
    const res = await rpc(cfg, fetchFn, 'ride_log_submit', { p_device: b.device_id.toLowerCase(), p_ride: ride, p_events: events });
    if (!res || !res.ok) return json(res && res.error === 'not_owner' ? 403 : 500, { ok: false, error: (res && res.error) || 'db' });
    return json(200, { ok: true, ride: ride.id, events: res.events || [] });
  } catch (e) {
    console.error('ride-log', e && e.message);
    return json(502, { ok: false, error: 'db-unavailable' });   // the phone keeps the taps and retries
  }
}

/* daily cron: keeps the free Supabase project from pausing and clears old rate-limit rows */
export async function keepalive(env, fetchFn = fetch) {
  const cfg = settings(env);
  if (!cfg.url || !cfg.key) return json(503, { ok: false, error: 'not-configured' });
  try { const n = await rpc(cfg, fetchFn, 'ride_log_ping', {}); return json(200, { ok: true, rides: n }); }
  catch (e) { return json(502, { ok: false, error: 'db-unavailable' }); }
}
