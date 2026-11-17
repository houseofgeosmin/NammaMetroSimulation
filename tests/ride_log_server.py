"""Local test server for the Timely Ride Log: serves site/ and a stand-in for /api/ride-log that follows the same rules
as supabase/schema.sql (access code, ride owned by its device, events stored once by id, undone flag can change).

Use from a test:   srv = start()  ->  srv.url, srv.state (dict), srv.cfg['delay'|'fail'], srv.stop()
Run by hand:       python tests/ride_log_server.py   (serves on http://localhost:8765, access code test-code)
"""
import json, threading, time
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / 'site'
CODE = 'test-code'

class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.webmanifest': 'application/manifest+json', '.js': 'text/javascript', '.woff2': 'font/woff2'}
    def log_message(self, *a): pass
    def end_headers(self):
        if self.path.startswith('/ride-log'): self.send_header('Cache-Control', 'no-cache')
        super().end_headers()
    def do_POST(self):
        srv = self.server
        if self.path != '/api/ride-log': return self._json(404, {'ok': False})
        body = self.rfile.read(int(self.headers.get('content-length') or 0))
        with srv.lock: srv.state['requests'] += 1
        if srv.cfg['drop']: self.close_connection = True; return   # like no signal: the connection dies, no answer
        if srv.cfg['delay']: time.sleep(srv.cfg['delay'])
        if srv.cfg['fail']: return self._json(502, {'ok': False, 'error': 'db-unavailable'})
        try: b = json.loads(body)
        except ValueError: return self._json(400, {'ok': False, 'error': 'bad-json'})
        if b.get('code') != CODE: return self._json(401, {'ok': False, 'error': 'bad-code'})
        ride, dev = b['ride'], b['device_id']
        with srv.lock:
            st = srv.state; old = st['rides'].get(ride['id'])
            if old and old['device_id'] != dev: return self._json(403, {'ok': False, 'error': 'not_owner'})
            st['rides'][ride['id']] = {**ride, 'device_id': dev}
            ok = []
            for e in b.get('events', []):
                st['event_posts'] += 1
                have = st['events'].get(e['id'])
                if have is None: st['events'][e['id']] = {**e, 'ride_id': ride['id']}; st['inserts'] += 1
                elif have['ride_id'] == ride['id']: have['undone'] = e['undone']; st['repeats'] += 1
                else: continue
                ok.append(e['id'])
        return self._json(200, {'ok': True, 'ride': ride['id'], 'events': ok})
    def _json(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code); self.send_header('content-type', 'application/json'); self.send_header('content-length', str(len(data))); self.end_headers()
        self.wfile.write(data)

def start(port=0):
    httpd = ThreadingHTTPServer(('127.0.0.1', port), partial(Handler, directory=str(SITE)))
    httpd.lock = threading.Lock(); httpd.cfg = {'delay': 0, 'fail': False, 'drop': False}
    httpd.state = {'rides': {}, 'events': {}, 'requests': 0, 'event_posts': 0, 'inserts': 0, 'repeats': 0}
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    httpd.url = f'http://localhost:{httpd.server_address[1]}'
    httpd.stop = lambda: (httpd.shutdown(), httpd.server_close())
    return httpd

if __name__ == '__main__':
    s = start(8765); print('serving', s.url, '(Ctrl-C to stop)')
    try: threading.Event().wait()
    except KeyboardInterrupt: s.stop()
