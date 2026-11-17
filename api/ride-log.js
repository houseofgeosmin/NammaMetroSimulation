/* POST /api/ride-log : upload a ride and its taps (see _ride-log-core.js). */
import { handle } from './_ride-log-core.js';
export function POST(request) { return handle(request, process.env); }
export function GET() { return new Response(JSON.stringify({ ok: false, error: 'method' }), { status: 405, headers: { 'content-type': 'application/json', allow: 'POST' } }); }
