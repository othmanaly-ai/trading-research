import { Component, Suspense, lazy, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useLiveJson } from "../useLiveJson";
import type { TowerSpec } from "./CityView";
import QualityPanel from "./QualityPanel";

// Read-only market monitoring (trading/monitor). The worker is a separate process; this view only
// displays its records from /api/monitor. Not a research dataset, not a trading signal.

const CityView = lazy(() => import("./CityView"));

interface SymbolRow {
  symbol: string; feed: string; feed_label: string; last_bar_start_utc: string | null; last_bar_end_utc: string | null;
  received_utc: string | null; close: number | null; volume: number | null; source_age_s: number | null;
  session_bars: number; freshness: string; freshness_detail: string;
}
interface Bar { t_utc: string; o: number; h: number; l: number; c: number; v: number; received_utc: string }
interface MonitorData {
  label: string; now_utc: string; reserved_end: string;
  market: { open: boolean; reason: string; next_open_utc: string | null; session_date: string | null; session_close_utc: string | null };
  worker: {
    pid: number | null; state: string; detail: string; started_utc: string | null; heartbeat_utc: string | null;
    heartbeat_age_s: number | null; alive: boolean; effective_state: string; stopped_utc: string | null;
    exit_reason: string | null; last_poll_utc: string | null; last_success_utc: string | null; next_poll_utc: string | null;
    consecutive_failures: number; backoff_until_utc: string | null; polls: number; requests: number;
    bars_inserted: number; duplicates_ignored: number; reserved_discarded: number;
  };
  desired: string; config: { symbols: string[]; feed: string; poll_seconds: number };
  symbols: SymbolRow[]; events: { id: number; ts_utc: string; level: string; kind: string; message: string }[];
  recent_bars: Record<string, Bar[]>; controls: Record<string, string>;
}

const FRESH_COLORS: Record<string, number> = {
  FRESH: 0x22c55e, STALE: 0xf59e0b, STOPPED: 0x334155, "MARKET CLOSED": 0x64748b, DISCONNECTED: 0xef4444, PAUSED: 0x818cf8, "NO DATA YET": 0x0ea5e9,
};
const WORKER_COLORS: Record<string, number> = {
  running: 0x22c55e, market_closed: 0x64748b, paused: 0x818cf8, disconnected: 0xef4444, error: 0xef4444,
  refused: 0xef4444, starting: 0x0ea5e9, stopped: 0x334155, "not running": 0x7f1d1d,
};

function et(ts: string | null): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleString("en-US", { timeZone: "America/New_York", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }) + " ET";
}
function age(s: number | null): string {
  if (s === null) return "—";
  if (s < 120) return `${s} s`;
  if (s < 7200) return `${Math.floor(s / 60)} min`;
  return `${Math.floor(s / 3600)} h`;
}

class Boundary extends Component<{ onError: (m: string) => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(e: Error) { this.props.onError(`3D view crashed (${e.message}). Showing the table.`); }
  render() { return this.state.failed ? null : this.props.children; }
}

export default function MonitorView({ reducedMotion }: { reducedMotion: boolean }) {
  const [tick, setTick] = useState(0);
  useEffect(() => { const id = setInterval(() => setTick((t) => t + 1), 2000); return () => clearInterval(id); }, []);
  const { data, error } = useLiveJson<MonitorData>("/api/monitor", tick);
  const [view, setView] = useState<"3D" | "Table">(
    () => (new URLSearchParams(window.location.search).get("3d") === "off" ? "Table" : "3D"));
  const [cityError, setCityError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ tone: string; text: string } | null>(null);
  const onCityFailure = useCallback((m: string) => { setCityError(m); setView("Table"); }, []);

  const towers = useMemo<TowerSpec[]>(() => {
    if (!data) return [];
    const w = data.worker;
    const workerTower: TowerSpec = {
      id: "worker", color: WORKER_COLORS[w.effective_state] ?? 0x334155,
      lines: [
        { cls: "tl-tag mon-tag", text: "MONITOR WORKER" },
        { cls: "tl-name", text: w.alive ? `pid ${w.pid}` : "no live worker" },
        { cls: "tl-status", text: w.effective_state.toUpperCase().replace("_", " ") },
        { cls: "tl-inst", text: `desired: ${data.desired}` },
        { cls: "tl-inst", text: `heartbeat ${age(w.heartbeat_age_s)} ago` },
      ],
      ariaLabel: `Monitoring worker: ${w.effective_state}. Show details.`, pulseKey: `${w.polls}:${w.effective_state}`,
    };
    return [workerTower, ...data.symbols.map((r) => ({
      id: r.symbol, color: FRESH_COLORS[r.freshness] ?? 0x64748b,
      lines: [
        { cls: "tl-tag mon-tag", text: `LIVE · ${r.feed.toUpperCase()}` },
        { cls: "tl-name", text: r.symbol },
        { cls: "tl-status", text: r.freshness },
        { cls: "tl-pnl", text: r.close !== null ? `last close ${r.close.toFixed(2)}` : "no bar" },
        { cls: "tl-inst", text: `bar ${et(r.last_bar_start_utc)}` },
        { cls: "tl-sim", text: "read-only · not a signal" },
      ],
      ariaLabel: `${r.symbol} ${r.feed}: ${r.freshness}. Show details.`, pulseKey: r.last_bar_start_utc ?? "",
    }))];
  }, [data]);

  const control = async (action: "start" | "pause" | "stop") => {
    setBusy(true);
    try {
      const r = await fetch("/api/monitor/control", { method: "POST", body: JSON.stringify({ action }),
        headers: { "Content-Type": "application/json", "X-Dashboard-Control": "1" } });
      const b = await r.json().catch(() => ({}));
      setNotice(r.ok ? { tone: "ok", text: b.note } : { tone: "danger", text: `Refused (HTTP ${r.status}): ${b.error}` });
    } catch (e) {
      setNotice({ tone: "danger", text: `Request failed: ${(e as Error).message}` });
    } finally {
      setBusy(false);
      setTick((t) => t + 1);
    }
  };

  if (error) return <p className="error panel">Could not load monitoring status: {error}</p>;
  if (!data) return <p className="empty panel">Loading monitoring status…</p>;
  const w = data.worker;
  const sel = selected && selected !== "worker" ? data.symbols.find((s) => s.symbol === selected) : null;

  return (
    <section className="panel wide monitor" aria-label="Market monitor">
      <div className="mon-banner"><strong>LIVE MARKET MONITOR · READ-ONLY</strong> Alpaca market data, {data.config.feed.toUpperCase()} feed
        ({data.symbols[0]?.feed_label}). Not a research dataset, not a trading signal, no recommendations. Order submission is DISABLED.
        Reserved research periods (through {data.reserved_end}) are never fetched.</div>

      <div className="row">
        <span>Market: <strong className={data.market.open ? "tone-ok" : ""}>{data.market.open ? "OPEN" : "CLOSED"}</strong>
          {data.market.open ? ` (session ${data.market.session_date}, closes ${et(data.market.session_close_utc)})`
            : ` (${data.market.reason}; next open ${et(data.market.next_open_utc)})`}</span>
      </div>
      <div className="row">
        <span>Worker: <strong className={w.alive ? "tone-ok" : "tone-danger"}>{w.effective_state.toUpperCase().replace("_", " ")}</strong>
          {" "}· desired <strong>{data.desired}</strong>{w.alive ? ` · pid ${w.pid}` : ""}</span>
        <button type="button" className="primary" disabled={busy} onClick={() => control("start")}>Start</button>
        <button type="button" disabled={busy} onClick={() => control("pause")}>Pause</button>
        <button type="button" disabled={busy} onClick={() => control("stop")}>Stop</button>
      </div>
      <p className="small muted">Start: {data.controls.start}. Pause: {data.controls.pause}. Stop: {data.controls.stop}.
        If the worker dies while the desired state is running, the dashboard relaunches it (at most once per 20 s, 6 per hour).</p>
      {notice && <p className={`notice tone-${notice.tone}`} role="status">{notice.text}</p>}
      <p className="small">{w.detail}</p>

      <div className="seg" role="tablist" aria-label="Monitor view">
        {(["3D", "Table"] as const).map((v) => (
          <button key={v} type="button" role="tab" aria-selected={view === v} className={view === v ? "on" : ""}
                  disabled={v === "3D" && !!cityError} onClick={() => setView(v)}>{v === "3D" ? "3D towers" : "Table"}</button>))}
      </div>
      {cityError && <p className="warn" role="alert">{cityError}</p>}
      {view === "3D" && !cityError && (
        <Boundary onError={onCityFailure}>
          <Suspense fallback={<p className="empty">Loading 3D view…</p>}>
            <CityView variant="monitor" towers={towers} coreColor={WORKER_COLORS[w.effective_state] ?? 0x334155}
                      selectedId={selected} onSelect={setSelected} reducedMotion={reducedMotion} onFailure={onCityFailure} />
          </Suspense>
        </Boundary>
      )}
      {view === "Table" && (
        <table className="mon-table" aria-label="Monitored symbols">
          <thead><tr><th>Symbol</th><th>Feed</th><th>Freshness</th><th>Last close</th><th>Volume</th><th>Bar start (source)</th>
            <th>Received</th><th>Age</th><th>Bars this session</th><th></th></tr></thead>
          <tbody>{data.symbols.map((r) => (
            <tr key={r.symbol} className={selected === r.symbol ? "sel" : ""}>
              <td>{r.symbol}</td><td>{r.feed}</td><td title={r.freshness_detail}>{r.freshness}</td>
              <td>{r.close?.toFixed(2) ?? "—"}</td><td>{r.volume ?? "—"}</td>
              <td>{et(r.last_bar_start_utc)}<br /><code className="small">{r.last_bar_start_utc ?? ""}</code></td>
              <td>{et(r.received_utc)}</td><td>{age(r.source_age_s)}</td><td>{r.session_bars}</td>
              <td><button type="button" aria-pressed={selected === r.symbol} onClick={() => setSelected(r.symbol)}>Details</button></td>
            </tr>))}</tbody>
        </table>
      )}

      {selected === "worker" || (!sel && selected === null) ? (
        <div className="job-detail" aria-label="Worker status">
          <h3>Worker status (persistent record)</h3>
          <dl className="kv">
            <dt>State</dt><dd>{w.state} (effective: {w.effective_state}); heartbeat {et(w.heartbeat_utc)} ({age(w.heartbeat_age_s)} ago)</dd>
            <dt>Process</dt><dd>pid {w.pid ?? "—"} · started {et(w.started_utc)} · stopped {et(w.stopped_utc)} {w.exit_reason ? `(${w.exit_reason})` : ""}</dd>
            <dt>Polling</dt><dd>every {data.config.poll_seconds} s · last {et(w.last_poll_utc)} · last success {et(w.last_success_utc)} · next {et(w.next_poll_utc)}</dd>
            <dt>Failures</dt><dd>{w.consecutive_failures} consecutive · backoff until {et(w.backoff_until_utc)}</dd>
            <dt>Totals</dt><dd>{w.polls} polls · {w.requests} requests · {w.bars_inserted} bars stored · {w.duplicates_ignored} duplicates ignored · {w.reserved_discarded} reserved-period bars discarded</dd>
          </dl>
        </div>
      ) : sel ? (
        <div className="job-detail" aria-label={`${sel.symbol} details`}>
          <h3>{sel.symbol} · {sel.feed} · {sel.freshness} <button type="button" className="small" onClick={() => setSelected(null)}>Close</button></h3>
          <p className="small">{sel.freshness_detail}. {sel.feed_label}.</p>
          <table aria-label={`Recent ${sel.symbol} bars`}><thead><tr><th>Bar start (ET)</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th><th>Received</th></tr></thead>
            <tbody>{(data.recent_bars[sel.symbol] ?? []).map((b) => (
              <tr key={b.t_utc}><td>{et(b.t_utc)}</td><td>{b.o}</td><td>{b.h}</td><td>{b.l}</td><td>{b.c}</td><td>{b.v}</td><td>{et(b.received_utc)}</td></tr>))}</tbody></table>
        </div>
      ) : null}

      <h3>Data quality: delayed SIP vs IEX (daily report)</h3>
      <QualityPanel tick={tick} />

      <h3>Events (state changes and errors)</h3>
      {data.events.length === 0 ? <p className="empty">No events recorded yet.</p> : (
        <table aria-label="Monitoring events"><thead><tr><th>Time</th><th>Level</th><th>Kind</th><th>Message</th></tr></thead>
          <tbody>{data.events.map((e) => (
            <tr key={e.id}><td>{et(e.ts_utc)}</td><td className={e.level === "error" ? "tone-danger" : ""}>{e.level}</td><td>{e.kind}</td><td>{e.message}</td></tr>))}</tbody></table>
      )}
    </section>
  );
}
