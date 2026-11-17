/* Timely Ride Log service worker, served from /ride-log-sw.js with scope /ride-log.
   build_site.py fills in VERSION (a hash of every cached file) and the ASSETS list, so any change makes a new cache. */
importScripts('/ride-log/queue.js');
const VERSION = '3bc1e083d75a';
const CACHE = 'ride-log-' + VERSION;
const ASSETS = ["/ride-log/", "/ride-log/queue.js", "/ride-log/manifest.webmanifest", "/ride-log/fonts/inter-latin.woff2", "/ride-log/fonts/space-grotesk-latin.woff2", "/ride-log/icons/apple-touch-icon.png", "/ride-log/icons/icon-192.png", "/ride-log/icons/icon-512.png", "/ride-log/icons/icon-maskable-512.png"];
const SHELL = '/ride-log/';

/* a redirected response cannot answer a navigation, so store a plain copy */
const plain = r => r.redirected ? r.blob().then(b => new Response(b, { status: 200, headers: r.headers })) : r;

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => Promise.all(ASSETS.map(u =>
    fetch(new Request(u, { cache: 'reload' })).then(r => { if (!r.ok) throw new Error(u + ' ' + r.status); return plain(r); }).then(r => c.put(u, r))
  ))));
  /* first install activates at once; updates wait until the page says no ride is in progress */
  if (!self.registration.active) self.skipWaiting();
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith('ride-log-') && k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('message', e => { if (e.data && e.data.type === 'skipWaiting') self.skipWaiting(); });

self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin || u.pathname.startsWith('/api/')) return;   // uploads always go to the network
  if (e.request.mode === 'navigate' && (u.pathname === '/ride-log' || u.pathname.startsWith('/ride-log/'))) {
    /* the page itself: from the cache, so it opens and reloads with no signal */
    e.respondWith(caches.open(CACHE).then(c => c.match(SHELL)).then(r => r || fetch(e.request)));
    return;
  }
  if (ASSETS.includes(u.pathname)) e.respondWith(caches.open(CACHE).then(c => c.match(u.pathname)).then(r => r || fetch(e.request)));
});

/* Background Sync: upload unsent taps even after the page is closed (Chrome/Android) */
async function flushAndTell() {
  const r = await self.RideLogQueue.flush();
  (await self.clients.matchAll({ includeUncontrolled: true })).forEach(c => c.postMessage({ type: 'flushed', result: r }));
  if (!r.ok && r.error !== 'no-code' && r.error !== 'bad-code') throw new Error('retry later');   // makes the browser retry the sync
}
self.addEventListener('sync', e => { if (e.tag === 'ride-log-sync') e.waitUntil(flushAndTell()); });
