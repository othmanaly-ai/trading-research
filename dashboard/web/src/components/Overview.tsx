import { Component, Suspense, lazy, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useLiveJson } from "../useLiveJson";
import type { Research } from "../types";
import type { TowerSpec } from "./CityView";

const CityView = lazy(() => import("./CityView"));

class Boundary extends Component<{ onError: (m: string) => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(e: Error) { this.props.onError(`3D district unavailable (${e.message}). The tables below hold the same information.`); }
  render() { return this.state.failed ? null : this.props.children; }
}

// Colours of the district: every one comes from a record (see the tables below for the same facts).
const C = { amber: 0xf59e0b, slate: 0x64748b, red: 0xef4444, teal: 0x14b8a6, cyan: 0x22d3ee, violet: 0x8b5cf6, deferred: 0x94a3b8, orange: 0xfb923c };
const FRESH: Record<string, number> = { FRESH: C.amber, STALE: C.orange, DISCONNECTED: C.red, "NO DATA YET": 0xfbbf24 };
const PIPE: Record<string, number> = { completed: C.teal, running: C.cyan, queued: C.slate, failed: C.red, cancelled: C.slate };

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

/** District ring around the command plaza: angle in degrees from straight behind the plaza (−z),
 *  negative to the left. Spans the back and both sides, so nothing stands between camera and centre. */
const RING_R = 32;
function ring(deg: number): [number, number] {
  const a = (deg * Math.PI) / 180;
  return [Math.round(Math.sin(a) * RING_R * 10) / 10, Math.round(-Math.cos(a) * RING_R * 10) / 10];
}

/** Map real components to buildings. Nothing here is invented: every status is a record field. */
function districtTowers(m: Mon | null, monError: string | null, jobs: Jobs | null, exps: Exps | null, rev: Rev | null): TowerSpec[] {
  const out: TowerSpec[] = [];
  const line = (cls: string, text: string) => ({ cls, text });
  out.push({ id: "server", archetype: "command", slot: [0, 0], color: monError ? C.red : C.cyan, category: "CITY SERVER",
    title: "Command: city server", status: monError ? "NOT RESPONDING" : "RESPONDING", pulseKey: "server",
    lines: [line("tl-name", "City server (dashboard + supervisor + job runner)"), line("tl-status", monError ? `not responding: ${monError}` : "responding"),
      line("tl-inst", "Serves records on 127.0.0.1; supervises the monitoring worker; runs research jobs")],
    ariaLabel: `City server: ${monError ? "not responding" : "responding"}. Show details.` });
  if (m) {
    const w = m.worker;
    const wc = !w.alive ? C.red : w.effective_state === "running" ? C.amber : C.slate;
    out.push({ id: "worker", archetype: "operations", slot: ring(-80), color: wc, category: "MARKET-DATA WORKER",
      title: "Monitoring worker", status: w.alive ? w.effective_state.toUpperCase().replace("_", " ") : "NOT RUNNING",
      dim: w.effective_state !== "running", links: ["server"], pulseKey: `${w.pid}:${w.effective_state}`,
      lines: [line("tl-name", w.alive ? `Worker pid ${w.pid}` : "Worker not running"), line("tl-status", w.effective_state),
        line("tl-inst", `desired ${m.desired} · heartbeat ${ageText(w.heartbeat_age_s)} ago · last success ${etTime(w.last_success_utc)}`)],
      ariaLabel: `Monitoring worker: ${w.effective_state}. Show details.` });
    const feedSlots: [number, number][] = [ring(-52), ring(-27), ring(-2)];
    m.symbols.forEach((sy, i) => out.push({ id: `feed-${sy.symbol}`, archetype: "finned", slot: feedSlots[i] ?? ring(-2 + (i - 2) * 25),
      color: FRESH[sy.freshness] ?? C.slate, category: "IEX LIVE FEED", title: sy.symbol, status: sy.freshness,
      dim: !(sy.freshness in FRESH), links: ["worker"], pulseKey: sy.last_bar_end_utc ?? "",
      lines: [line("tl-name", `${sy.symbol} (IEX, live)`), line("tl-status", sy.freshness),
        line("tl-inst", `latest bar end ${etTime(sy.last_bar_end_utc)} · data age ${ageText(sy.source_age_s)}`)],
      ariaLabel: `${sy.symbol} feed: ${sy.freshness}. Show details.` }));
  }
  if (jobs) {
    const latest = jobs.pipelines[jobs.pipelines.length - 1];
    out.push({ id: "jobs", archetype: "terraced", slot: ring(22), color: latest ? PIPE[latest.status] ?? C.slate : C.slate,
      category: "RESEARCH JOBS", title: "Research-job runner", status: latest ? `LATEST ${latest.status.toUpperCase()}` : "NO PIPELINES",
      dim: !latest || latest.status !== "running", links: ["server", "experiments"], pulseKey: latest ? `${latest.id}:${latest.status}` : "",
      lines: [line("tl-name", "Deterministic research jobs"), line("tl-status", latest ? `latest pipeline ${latest.status}` : "none"),
        line("tl-inst", `${jobs.pipelines.length} pipeline(s) on record; latest ${latest ? `${latest.experiment} at ${etTime(latest.created_utc)}` : "—"}`)],
      ariaLabel: `Research-job runner: ${latest?.status ?? "no pipelines"}. Show details.` });
  }
  if (exps) {
    const closed = exps.experiments.filter((e) => e.status?.closed).length;
    out.push({ id: "experiments", archetype: "paired", slot: ring(50), color: C.slate, category: "CLOSED EXPERIMENTS",
      title: `${exps.experiments.length} experiments`, status: `${closed} CLOSED`, dim: true, pulseKey: "experiments",
      lines: [line("tl-name", "Experiments 001 and 002"),
        ...exps.experiments.map((e) => line("tl-inst", `${e.experiment}: ${e.status ? `${e.status.state}${e.status.closed ? " (closed)" : ""}` : "status unreadable"}`))],
      ariaLabel: `Experiments: ${closed} closed. Show details.` });
    (exps.candidates ?? []).forEach((c, i) => out.push({ id: `cand-${c.candidate}`, archetype: "construction", slot: ring(-110 - i * 22),
      color: C.deferred, category: "DEFERRED CANDIDATE", title: c.candidate, status: c.status?.state === "DEFERRED_DATA_SEMANTICS" ? "DEFERRED" : c.status?.state ?? "unknown",
      dim: true, pulseKey: c.candidate,
      lines: [line("tl-name", `Candidate ${c.candidate} (not an experiment)`), line("tl-status", c.status?.state ?? "status unreadable"),
        ...(c.status?.blockers ?? []).map((b) => line("tl-inst", `Blocker: ${b}`))],
      ariaLabel: `Candidate ${c.candidate}: ${c.status?.state ?? "unknown"}. Show details.` }));
  }
  if (rev) {
    out.push({ id: "review", archetype: "twisted", slot: ring(80), color: C.violet, category: "OPTIONAL MODEL REVIEW",
      title: "Model review", status: rev.available ? "AVAILABLE" : "DISABLED", dim: !rev.available, links: ["jobs"], pulseKey: rev.state,
      lines: [line("tl-name", "Optional model review (paid calls)"), line("tl-status", rev.state),
        line("tl-inst", `${rev.revoked ? "owner authorization revoked" : "authorization present"} · spent this month $${rev.month_spent_usd.toFixed(2)}`)],
      ariaLabel: `Model review: ${rev.state}. Show details.` });
  }
  return out;
}

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

export default function Overview({ research, openView, reducedMotion = false }: { research: Research | null; openView: (v: string) => void; reducedMotion?: boolean }) {
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
  const towers = useMemo(() => districtTowers(m ?? null, mon.error, jobs.data, exps.data, rev.data),
    [m, mon.error, jobs.data, exps.data, rev.data]);
  const [sel, setSel] = useState<string | null>(null);
  const [cityError, setCityError] = useState<string | null>(() =>
    new URLSearchParams(window.location.search).get("3d") === "off" ? "3D district turned off (?3d=off)." : null);
  const onCityFailure = useCallback((msg: string) => setCityError(msg), []);
  const selTower = towers.find((t) => t.id === sel) ?? null;
  const OPEN: Record<string, string> = { worker: "Market monitor", jobs: "Research jobs", experiments: "Research jobs", review: "Research jobs", server: "Market monitor" };
  const openFor = sel ? OPEN[sel] ?? (sel.startsWith("feed-") ? "Market monitor" : sel.startsWith("cand-") ? "Research jobs" : null) : null;

  return (
    <section className="panel wide overview" aria-label="Operational overview">
      <h2>Operational overview</h2>
      <p className="small muted">Read from local records by the city server. Refreshes every 5–15 s while this page is open; nothing here runs when the page is closed.</p>

      <div className="district">
        {cityError ? <p className="warn">{cityError}</p> : (
          <Boundary onError={onCityFailure}>
            <Suspense fallback={<p className="empty">Loading 3D district…</p>}>
              <CityView variant="district" towers={towers} coreColor={null} selectedId={sel} onSelect={setSel}
                        reducedMotion={reducedMotion} onFailure={onCityFailure}
                        mode={{ label: "REAL RECORDS", tone: "real",
                          detail: m ? `read-only · market ${m.market.open ? "OPEN" : "CLOSED"} · no trading execution exists` : "read-only" }}
                        legend={[{ color: C.cyan, label: "City server (responding)" }, { color: C.amber, label: "Market data: running / fresh" },
                          { color: C.slate, label: "Closed market, idle or closed record" }, { color: C.teal, label: "Deterministic research jobs" },
                          { color: C.violet, label: "Optional model review (disabled)" }, { color: C.deferred, label: "Deferred candidate" },
                          { color: C.red, label: "Failed, refused or not running" }]} />
            </Suspense>
          </Boundary>
        )}
        {selTower && (
          <aside className="district-detail" aria-label={`Selected: ${selTower.title}`}>
            <h3>{selTower.category} · {selTower.title} <button type="button" className="small" onClick={() => setSel(null)}>Close</button></h3>
            <p><strong style={{ color: `#${selTower.color.toString(16).padStart(6, "0")}` }}>{selTower.status}</strong></p>
            <ul className="notes">{selTower.lines.map((l, i) => <li key={i}>{l.text}</li>)}</ul>
            {openFor && <button type="button" onClick={() => openView(openFor)}>Open {openFor} for full records</button>}
          </aside>
        )}
      </div>

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
