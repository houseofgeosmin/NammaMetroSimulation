/* GET /api/keepalive : called once a day by Vercel Cron (vercel.json) so the free Supabase project never pauses. */
import { keepalive } from './_ride-log-core.js';
export function GET() { return keepalive(process.env); }
