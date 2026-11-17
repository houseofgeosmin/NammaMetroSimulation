// Tests the real Vercel function logic (api/_ride-log-core.js) against a stand-in for Supabase's RPC endpoint that
// follows supabase/schema.sql. Run: node tests/test_api_core.mjs
import { handle, keepalive, codeHash, LIMITS } from '../api/_ride-log-core.js';
import { randomUUID } from 'node:crypto';

let fails = 0;
const check = (c, what) => { console.log((c ? 'ok   ' : 'FAIL ') + what); if (!c) fails++; };

function fakeSupabase() {
  const db = { rides: new Map(), events: new Map(), rate: new Map(), calls: [], headers: [] };
  db.fetch = async (url, init) => {
    const name = url.split('/rpc/')[1], a = JSON.parse(init.body);
    db.calls.push(name); db.headers.push(init.headers);
    const ok = v => new Response(JSON.stringify(v), { status: 200, headers: { 'content-type': 'application/json' } });
    if (name === 'ride_log_rate_hit') {
      const r = db.rate.get(a.p_key);
      const fresh = !r || Date.now() - r.start > a.p_window_s * 1000;
      const n = fresh ? 1 : r.hits + 1; db.rate.set(a.p_key, { start: fresh ? Date.now() : r.start, hits: n });
      return ok(n <= a.p_limit);
    }
    if (name === 'ride_log_submit') {
      const r = a.p_ride, old = db.rides.get(r.id);
      if (old && old.device_id !== a.p_device) return ok({ ok: false, error: 'not_owner' });
      db.rides.set(r.id, { ...r, device_id: a.p_device, done: (old && old.done) || r.done });
      const ids = [];
      for (const e of a.p_events) {
        const have = db.events.get(e.id);
        if (!have) db.events.set(e.id, { ...e, ride_id: r.id }); else if (have.ride_id === r.id) have.undone = e.undone; else continue;
        ids.push(e.id);
      }
      return ok({ ok: true, events: ids });
    }
    if (name === 'ride_log_ping') return ok(db.rides.size);
    return new Response('no such function', { status: 404 });
  };
  return db;
}

const CODE = 'abcd-efgh-jkmn';
const ENV = { SUPABASE_URL: 'https://example.supabase.co/', SUPABASE_SERVICE_ROLE_KEY: 'eyJ.legacy.jwt', RIDE_LOG_CODE_SHA256: codeHash(CODE) };
const now = Date.now();
const ride = (o = {}) => ({ id: randomUUID(), nick: 'Asha', date: '2026-11-18', weekday: 'Wed', service: 'weekday', line: 'G', dir: 0, towards: 'Silk Institute',
  option_index: 3, pattern_index: 2, from_station: 52, from_name: 'Majestic', matched_profile: 10, matched_start: 30000, start_ts: now, end_ts: null, done: false, ...o });
const ev = (o = {}) => ({ id: randomUUID(), kind: 'stop', station_index: 52, sec_ist: 33012.4, client_ts: now, undone: false, ...o });
const post = (body, env = ENV, db, ip = '1.2.3.4') => handle(new Request('https://x/api/ride-log', { method: 'POST', headers: { 'content-type': 'application/json', 'x-forwarded-for': ip },
  body: typeof body === 'string' ? body : JSON.stringify(body) }), env, db.fetch);

const db = fakeSupabase(), dev = randomUUID(), r = ride(), e1 = ev(), e2 = ev({ kind: 'open', sec_ist: 33020 });
let res = await post({ code: CODE, device_id: dev, ride: r, events: [e1, e2] }, ENV, db), j = await res.json();
check(res.status === 200 && j.ok && j.ride === r.id && j.events.length === 2, 'valid upload accepted, both event ids confirmed');
check(db.headers[0].authorization === 'Bearer eyJ.legacy.jwt' && db.headers[0].apikey, 'legacy service key sent as apikey + bearer');
res = await post({ code: CODE, device_id: dev, ride: r, events: [e1, e2] }, ENV, db); j = await res.json();
check(res.status === 200 && db.events.size === 2, 'retrying the same upload creates no duplicates');
res = await post({ code: CODE, device_id: dev, ride: { ...r, done: true }, events: [{ ...e2, undone: true }] }, ENV, db);
check(res.status === 200 && db.events.get(e2.id).undone === true && db.rides.get(r.id).done, 'undo flag and finished ride update the same rows');
res = await post({ code: CODE, device_id: randomUUID(), ride: r, events: [ev()] }, ENV, db); j = await res.json();
check(res.status === 403 && j.error === 'not_owner' && db.events.size === 2, "another device cannot change someone else's ride");
res = await post({ code: 'wrong', device_id: dev, ride: ride(), events: [] }, ENV, db); j = await res.json();
check(res.status === 401 && j.error === 'bad-code', 'wrong access code refused');
res = await post({ device_id: dev, ride: ride(), events: [] }, ENV, db);
check(res.status === 401, 'missing access code refused');
res = await post('{not json', ENV, db); check(res.status === 400, 'broken JSON refused');
for (const [bad, what] of [[{ line: 'X' }, 'unknown line'], [{ id: 'not-a-uuid' }, 'bad ride id'], [{ dir: 2 }, 'bad direction'], [{ date: 'yesterday' }, 'bad date']]) {
  res = await post({ code: CODE, device_id: dev, ride: ride(bad), events: [] }, ENV, db); check(res.status === 400, 'refused: ' + what);
}
for (const [bad, what] of [[{ kind: 'dance' }, 'unknown tap kind'], [{ sec_ist: 90000 }, 'time past midnight'], [{ id: '1' }, 'bad event id']]) {
  res = await post({ code: CODE, device_id: dev, ride: ride(), events: [ev(bad)] }, ENV, db); check(res.status === 400, 'refused: ' + what);
}
res = await post({ code: CODE, device_id: dev, ride: ride(), events: Array.from({ length: 501 }, () => ev()) }, ENV, db); check(res.status === 400, 'refused: more than 500 taps in one request');
const r2 = ride({ nick: '<b>Ashaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa</b>', email: 'x@y.z', phone: '999' });
res = await post({ code: CODE, device_id: dev, ride: r2, events: [] }, ENV, db);
const stored = db.rides.get(r2.id);
check(res.status === 200 && stored.nick.length <= 24 && !stored.nick.includes('<') && !('email' in stored) && !('phone' in stored), 'only the allowed fields are stored, name trimmed and cleaned');
res = await post({ code: CODE, device_id: dev, ride: ride(), events: [] }, { ...ENV, RIDE_LOG_CODE_SHA256: '' }, db); check(res.status === 503, 'not configured -> 503 (phone keeps the taps)');
res = await handle(new Request('https://x/api/ride-log', { method: 'GET' }), ENV, db.fetch); check(res.status === 405, 'GET refused');

// rate limits
const db2 = fakeSupabase(); let codes = [];
for (let i = 0; i < LIMITS.badCodePerHour + 2; i++) codes.push((await post({ code: 'guess' + i, device_id: dev, ride: ride(), events: [] }, ENV, db2, '9.9.9.9')).status);
check(codes.slice(0, LIMITS.badCodePerHour).every(s => s === 401) && codes.at(-1) === 429, `wrong-code guessing is rate limited after ${LIMITS.badCodePerHour} tries`);
const db3 = fakeSupabase(); codes = [];
for (let i = 0; i < LIMITS.devicePer10Min + 1; i++) codes.push((await post({ code: CODE, device_id: dev, ride: ride(), events: [] }, ENV, db3, '5.5.5.' + (i % 200))).status);
check(codes.at(-1) === 429 && codes.at(-2) === 200, `one phone is rate limited after ${LIMITS.devicePer10Min} uploads per 10 min`);
check(![...db3.rate.keys()].some(k => k.includes('5.5.5')), 'rate-limit keys are hashed, no IP addresses stored');

// new-style secret key, and the keep-alive
const db4 = fakeSupabase();
await post({ code: CODE, device_id: dev, ride: ride(), events: [] }, { ...ENV, SUPABASE_SERVICE_ROLE_KEY: '', SUPABASE_SECRET_KEY: 'sb_secret_abc' }, db4);
check(db4.headers[0].apikey === 'sb_secret_abc' && !db4.headers[0].authorization, 'new sb_secret_ key sent as apikey only');
res = await keepalive(ENV, db.fetch); j = await res.json(); check(res.status === 200 && j.ok && j.rides >= 1, 'keep-alive pings the database');
const down = async () => { throw new TypeError('fetch failed'); };
res = await handle(new Request('https://x/api/ride-log', { method: 'POST', body: JSON.stringify({ code: CODE, device_id: dev, ride: ride(), events: [] }) }), ENV, down);
check(res.status === 502, 'database down -> 502, the phone retries later');

console.log(fails ? `FAILED: ${fails}` : 'ALL PASSED'); process.exit(fails ? 1 : 0);
