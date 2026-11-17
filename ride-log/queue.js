/* Timely Ride Log: phone storage and upload queue. Shared by the page (script tag) and the service worker (importScripts).
   IndexedDB "timely-ride-log":
     kv      key -> value      device_id, code, nick, current (id of the ride in progress)
     rides   keyPath id        ride fields + rev (bumped on every change) + sentRev (last rev the server confirmed)
     events  keyPath id        {id, ride_id, k, st, sec, ts, undone, ver, sentVer}; index by_ride
   Every ride and event has a client-made UUID, so a retried upload can never create a duplicate on the server. */
(function (root) {
  'use strict';
  const DB_NAME = 'timely-ride-log', DB_VER = 1, ENDPOINT = '/api/ride-log', BATCH = 400;
  let dbp = null;
  function open() {
    if (dbp) return dbp;
    dbp = new Promise((res, rej) => {
      const rq = indexedDB.open(DB_NAME, DB_VER);
      rq.onupgradeneeded = () => {
        const db = rq.result;
        if (!db.objectStoreNames.contains('kv')) db.createObjectStore('kv');
        if (!db.objectStoreNames.contains('rides')) db.createObjectStore('rides', { keyPath: 'id' });
        if (!db.objectStoreNames.contains('events')) db.createObjectStore('events', { keyPath: 'id' }).createIndex('by_ride', 'ride_id');
      };
      rq.onsuccess = () => { const db = rq.result; db.onversionchange = () => { db.close(); dbp = null; }; res(db); };
      rq.onerror = () => { dbp = null; rej(rq.error); };
      rq.onblocked = () => rej(new Error('storage blocked by another tab'));
    });
    return dbp;
  }
  const done = tx => new Promise((res, rej) => { tx.oncomplete = () => res(); tx.onerror = () => rej(tx.error); tx.onabort = () => rej(tx.error || new Error('aborted')); });
  const req = r => new Promise((res, rej) => { r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });

  function uuid() {
    if (root.crypto && crypto.randomUUID) return crypto.randomUUID();
    const b = crypto.getRandomValues(new Uint8Array(16)); b[6] = (b[6] & 15) | 64; b[8] = (b[8] & 63) | 128;
    const h = [...b].map(x => x.toString(16).padStart(2, '0')).join('');
    return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
  }

  async function kvGet(k) { const db = await open(); return req(db.transaction('kv').objectStore('kv').get(k)); }
  async function kvSet(k, v) { const db = await open(); const tx = db.transaction('kv', 'readwrite'); tx.objectStore('kv').put(v, k); return done(tx); }
  async function deviceId() { let d = await kvGet('device_id'); if (!d) { d = uuid(); await kvSet('device_id', d); } return d; }

  /* write a ride and any events in ONE transaction; resolves when the data is on disk */
  async function put(ride, events) {
    const db = await open(); const tx = db.transaction(['rides', 'events'], 'readwrite');
    if (ride) tx.objectStore('rides').put(ride);
    (events || []).forEach(e => tx.objectStore('events').put(e));
    return done(tx);
  }
  async function getRide(id) { const db = await open(); return req(db.transaction('rides').objectStore('rides').get(id)); }
  async function allRides() { const db = await open(); return req(db.transaction('rides').objectStore('rides').getAll()); }
  async function eventsOf(id) { const db = await open(); return req(db.transaction('events').objectStore('events').index('by_ride').getAll(id)); }

  const rideUnsent = r => (r.sentRev || 0) < r.rev;
  const evUnsent = e => (e.sentVer || 0) < e.ver;
  async function unsentCount() {
    const db = await open(); const tx = db.transaction(['rides', 'events']);
    const [rs, es] = await Promise.all([req(tx.objectStore('rides').getAll()), req(tx.objectStore('events').getAll())]);
    return { events: es.filter(evUnsent).length, rides: rs.filter(rideUnsent).length };
  }

  /* the ride fields the server stores (only a first name, stations and times) */
  const rideBody = r => ({ id: r.id, nick: r.nick, date: r.date, weekday: r.dow, service: r.svc, line: r.line, dir: r.dir, towards: r.towards,
    option_index: r.opt, pattern_index: r.pat, from_station: r.from, from_name: r.fromName,
    matched_profile: r.matched ? r.matched.prof : null, matched_start: r.matched ? r.matched.start : null,
    start_ts: r.startTs, end_ts: r.endTs || null, done: !!r.done });
  const eventBody = e => ({ id: e.id, kind: e.k, station_index: e.st, sec_ist: e.sec, client_ts: e.ts, undone: !!e.undone });

  /* upload everything unsent, ride by ride. Returns {ok, sent, remaining, status, error}.
     Only rows the server confirmed (by id, and still at the version we sent) are marked sent. */
  let running = null;
  function flush(opt) { if (!running) running = doFlush(opt || {}).finally(() => { running = null; }); return running; }
  async function doFlush(opt) {
    const fetchFn = opt.fetch || root.fetch.bind(root), endpoint = opt.endpoint || ENDPOINT;
    const code = await kvGet('code'), device = await deviceId();
    let sent = 0, status = 0, error = null;
    const rides = await allRides();
    for (const r of rides) {
      const evs = (await eventsOf(r.id)).filter(evUnsent);
      if (!rideUnsent(r) && !evs.length) continue;
      if (!code) { error = 'no-code'; break; }
      for (let i = 0; i < Math.max(1, evs.length); i += BATCH) {
        const batch = evs.slice(i, i + BATCH), rev = r.rev;
        let resp;
        try {
          resp = await fetchFn(endpoint, { method: 'POST', headers: { 'content-type': 'application/json' }, cache: 'no-store',
            body: JSON.stringify({ code, device_id: device, ride: rideBody(r), events: batch.map(eventBody) }) });
        } catch (e) { return finish(false, 0, 'offline'); }
        status = resp.status;
        if (!resp.ok) { let j = null; try { j = await resp.json(); } catch (e) {} return finish(false, status, (j && j.error) || 'http-' + status); }
        const j = await resp.json().catch(() => null);
        if (!j || !j.ok) return finish(false, status, (j && j.error) || 'bad-response');
        const okIds = new Set(j.events || []);
        /* mark confirmed rows, but only if they did not change while the request was in flight */
        const db = await open(); const tx = db.transaction(['rides', 'events'], 'readwrite');
        const rs = tx.objectStore('rides'), es = tx.objectStore('events');
        const cur = await req(rs.get(r.id));
        if (cur && cur.rev === rev && j.ride === r.id) { cur.sentRev = rev; rs.put(cur); }
        for (const e of batch) {
          if (!okIds.has(e.id)) continue;
          const c = await req(es.get(e.id));
          if (c && c.ver === e.ver) { c.sentVer = e.ver; es.put(c); sent++; }
        }
        await done(tx);
      }
    }
    return finish(!error, status, error);
    async function finish(ok, st, err) { const u = await unsentCount(); return { ok, sent, remaining: u.events + u.rides, unsentEvents: u.events, status: st, error: err }; }
  }

  root.RideLogQueue = { open, uuid, kvGet, kvSet, deviceId, put, getRide, allRides, eventsOf, unsentCount, flush, rideUnsent, evUnsent, ENDPOINT };
})(typeof self !== 'undefined' ? self : this);
