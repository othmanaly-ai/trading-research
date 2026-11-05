import { useEffect, useState } from "react";
import { useLiveJson } from "../useLiveJson";
import type { Research } from "../types";

// Operational overview built only from existing read-only endpoints. It adds no polling of any
// external service: every request goes to the local city server, which reads local records.

interface Mon {
  now_utc: string; desired: string;
  market: { open: boolean; reason: string; next_open_utc: string | null; session_date: string | null; session_close_utc: string | null };
  worker: { pid: number | null; alive: boolean; effective_state: string; heartbeat_age_s: number | null; last_success_utc: string | null;
            consecutive_failures: number };
  symbols: { symbol: string; freshness: string; last_bar_end_utc: string | null; source_age_s: number | null }[];
}
interface Sess { sessions: { session_date: string; state: string; report_versions: number }[] }
interface Jobs { pipelines: { id: string; experiment: string; status: string; created_utc: string }[] }
interface Exps {
  experiments: { experiment: string; status: { state: string; closed: boolean; failed_rules: string[] | null } | null }[];
  candidates?: { candidate: string; status: { state: string; performance_evaluated: boolean; blockers: string[]; downloads: string } | null }[];
}
interface Rev { available: boolean; state: string; revoked: boolean; month_spent_usd: number }

export function etTime(ts: string | number | null | undefined, withDate = true): string {
  if (ts === null || ts === undefined) return "—";
  return new Date(ts).toLocaleString("en-US", { timeZone: "America/New_York", ...(withDate ? { month: "short", day: "numeric" } : {}),
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }) + " ET";
}
export function ageText(s: number | null | undefined): string {
  if (s === null || s === undefined) return "—";
  if (s < 120) return `${Math.round(s)} s`;
  if (s < 7200) return `${Math.floor(s / 60)} min`;
  return `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min`;
}

export default function Overview({ research, openView }: { research: Research | null; openView: (v: string) => void }) {
  const [tick, setTick] = useState(0);
  useEffect(() => { const id = setInterval(() => setTick((t) => t + 1), 5000); return () => clearInterval(id); }, []);
  const slow = Math.floor(tick / 3);
  const mon = useLiveJson<Mon>("/api/monitor", tick);
  const sess = useLiveJson<Sess>("/api/monitor/sessions", slow);
  const jobs = useLiveJson<Jobs>("/api/jobs", slow);
  const exps = useLiveJson<Exps>("/api/experiments", slow);
  const rev = useLiveJson<Rev>("/api/reviewer/status", slow);

  const m = mon.data, w = m?.worker;
  const latest = sess.data?.sessions[0];
  const byStatus: Record<string, number> = {};
  for (const p of jobs.data?.pipelines ?? []) byStatus[p.status] = (byStatus[p.status] ?? 0) + 1;
  const gate = research?.order_submission;

  return (
    <section className="panel wide overview" aria-label="Operational overview">
      <h2>Operational overview</h2>
      <p className="small muted">Read from local records by the city server. Refreshes every 5–15 s while this page is open; nothing here runs when the page is closed.</p>

      <div className="ov-grid">
        <div className="ov-card" aria-label="Server and worker health">
          <h3>Server and monitoring worker</h3>
          {mon.error ? <p className="tone-danger">City server not responding: {mon.error}</p> : !m || !w ? <p className="empty">Loading…</p> : (<>
            <p><strong className="tone-ok">City server responding</strong> · server clock {etTime(m.now_utc)}</p>
            <p>Worker: <strong className={w.alive ? "tone-ok" : "tone-danger"}>{w.alive ? "RUNNING" : "NOT RUNNING"}</strong>
              {w.alive ? ` (pid ${w.pid}, heartbeat ${ageText(w.heartbeat_age_s)} ago)` : ` (${w.effective_state})`} · desired state {m.desired}</p>
            <p>Market: <strong>{m.market.open ? "OPEN" : "CLOSED"}</strong>
              {m.market.open ? ` · closes ${etTime(m.market.session_close_utc)}` : ` · ${m.market.reason} · next open ${etTime(m.market.next_open_utc)}`}</p>
            <p className="small">Latest IEX bar end: {m.symbols.map((s) => `${s.symbol} ${etTime(s.last_bar_end_utc, false)} (${s.freshness})`).join(" · ")}</p>
            <p className="small">Last successful poll {etTime(w.last_success_utc)} · {w.consecutive_failures} current failure(s)</p>
            {latest && <p className="small">Latest monitored session {latest.session_date}: <strong>{latest.state.toUpperCase().replace("_", " ")}</strong> · {latest.report_versions} stored report version(s)</p>}
            <button type="button" onClick={() => openView("Market monitor")}>Open Market monitor</button>
          </>)}
        </div>

        <div className="ov-card" aria-label="Research status">
          <h3>Research</h3>
          {exps.data ? (<>
            <table className="q-table"><thead><tr><th>Item</th><th>State</th></tr></thead><tbody>
              {exps.data.experiments.map((e) => (
                <tr key={e.experiment}><td><code>{e.experiment}</code></td>
                  <td>{e.status ? `${e.status.state}${e.status.closed ? " · CLOSED" : ""}` : "status unreadable"}</td></tr>))}
              {(exps.data.candidates ?? []).map((c) => (
                <tr key={c.candidate}><td><code>{c.candidate}</code> (candidate, not an experiment)</td>
                  <td>{c.status ? `${c.status.state}${c.status.performance_evaluated ? "" : " · never evaluated on performance"}` : "status unreadable"}</td></tr>))}
            </tbody></table>
            {(exps.data.candidates ?? []).filter((c) => c.status?.blockers.length).map((c) => (
              <p key={c.candidate} className="small">Blocker ({c.candidate}): {c.status!.blockers[0]}{c.status!.blockers.length > 1 ? ` (+${c.status!.blockers.length - 1} more)` : ""}.</p>))}
          </>) : <p className="empty">{exps.error ? `Could not load: ${exps.error}` : "Loading…"}</p>}
          <p className="small">Research-job pipelines on record: {jobs.data ? (Object.keys(byStatus).length ? Object.entries(byStatus).map(([k, v]) => `${v} ${k}`).join(" · ") : "none") : "…"}</p>
          <button type="button" onClick={() => openView("Research jobs")}>Open Research jobs</button>
        </div>

        <div className="ov-card" aria-label="Safety status">
          <h3>Safety status</h3>
          <p>Order submission: <strong className="tone-ok">{gate ? (gate.enabled ? "ENABLED (unexpected)" : "DISABLED") : "…"}</strong>
            {gate ? ` · trading mode ${gate.trading_mode}` : ""}</p>
          {gate && <p className="small">{gate.note}</p>}
          <p>Paid model review: <strong className={rev.data?.available ? "tone-warn" : "tone-ok"}>{rev.data ? rev.data.state : "…"}</strong>
            {rev.data?.revoked ? " · owner authorization revoked" : ""}{rev.data ? ` · spent this month $${rev.data.month_spent_usd.toFixed(2)}` : ""}</p>
          <p className="small">Held-out research periods (validation, final) are never fetched; monitoring refuses dates through 2026-10-30.</p>
        </div>
      </div>

      <h3>What keeps running, and what stops</h3>
      <table className="q-table" aria-label="What stops when">
        <thead><tr><th>Event</th><th>Effect</th></tr></thead>
        <tbody>
          <tr><td>Computer sleeps, hibernates or shuts down</td><td>The city server and the monitoring worker stop. No market data is requested. Minutes missed live are permanently missing from the live record.</td></tr>
          <tr><td>The Claude desktop app closes</td><td>The terminal tab that runs the city server closes, so the server and worker stop.</td></tr>
          <tr><td>The city server stops (tab closed, Ctrl+C)</td><td>The worker stops with it, and nothing restarts either one until you start the server again.</td></tr>
          <tr><td>The worker crashes while the server runs</td><td>The server's supervisor relaunches it (at most once per 20 s and 6 times per hour).</td></tr>
          <tr><td>Server started again later</td><td>Unfinished sessions within the last 5 trading sessions are compared and finalized; live gaps stay gaps.</td></tr>
        </tbody>
      </table>
      <p className="small warn">Not provided: no Windows startup task, no 24/7 service, no notifications and no automatic follow-up. Someone has to start the server and check the reports.</p>
    </section>
  );
}
